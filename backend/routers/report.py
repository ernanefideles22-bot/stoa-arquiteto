from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import base64, json, traceback, datetime
from ..models.database import get_db, Project, Terrain, Topography, Implantation, Financial
from ..services import ai_engine
from ..services.errors import error_detail, debug_or_none

router = APIRouter(prefix="/api/report", tags=["report"])

class ReportRequest(BaseModel):
    project_id: int

@router.post("/generate")
async def generate_report(data: ReportRequest, db: Session = Depends(get_db)):
    try:
        project = db.query(Project).filter(Project.id == data.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Projeto nao encontrado")

        terrain = db.query(Terrain).filter(Terrain.project_id == data.project_id).first()
        topo    = db.query(Topography).filter(Topography.project_id == data.project_id).first()
        imp     = db.query(Implantation).filter(Implantation.project_id == data.project_id, Implantation.is_selected == True).first()
        if imp is None:
            imp = db.query(Implantation).filter(Implantation.project_id == data.project_id).first()
        fin     = db.query(Financial).filter(Financial.project_id == data.project_id).first()

        project_data = {
            "nome": project.name,
            "descricao": project.description or "",
            "terreno": None,
            "implantacao": None,
            "financeiro": None,
        }
        if terrain:
            project_data["terreno"] = {
                "area_ha": terrain.area_ha,
                "municipio": terrain.city,
                "zona_uso": terrain.zoneamento,
            }
        if imp:
            project_data["implantacao"] = {
                "num_lotes": imp.num_lotes,
                "area_media_lote": imp.area_media_lote,
            }
        # Numeros vem das colunas dedicadas do Financial (ja populadas corretamente
        # em backend/routers/financial.py), nao de um round-trip via analise_ia --
        # esse campo texto guarda so recomendacoes/alertas qualitativos da IA.
        if fin:
            project_data["financeiro"] = {
                "vgv":           fin.vgv or 0,
                "lucro_bruto":   fin.lucro_bruto or 0,
                "margem_bruta":  fin.margem_bruta or 0,
                "roi":           fin.roi or 0,
                "payback_meses": fin.payback_meses or 0,
            }

        resumo = ""
        resumo_error = None
        try:
            resumo = await ai_engine.gerar_resumo_executivo(project_data)
        except Exception as e:
            resumo_error = str(e)
            # Mensagem generica pro usuario; o erro real vai pro log e, em modo
            # debug, pro campo debug_resumo_error.
            resumo = "Resumo executivo indisponivel no momento (falha ao consultar a IA)."

        pdf_b64  = None
        pdf_error = None
        try:
            pdf_b64 = _build_pdf(project, terrain, topo, imp, fin, resumo, project_data)
        except Exception as e:
            pdf_error = traceback.format_exc()

        return {
            "resumo_executivo": resumo,
            "pdf_base64": pdf_b64,
            "has_terrain": terrain is not None,
            "has_topo": topo is not None,
            "has_implantacao": imp is not None,
            "has_financeiro": fin is not None,
            # Campos de debug so em modo debug -- traceback nao vaza em producao
            "debug_resumo_error": debug_or_none(resumo_error),
            "debug_pdf_error": debug_or_none(pdf_error),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_detail(e, "report_generate"))


# ── PDF BUILDER ──────────────────────────────────────────────────────────

def _safe(text) -> str:
    return str(text or "").encode("latin-1", errors="replace").decode("latin-1")

def _fmt_brl(value) -> str:
    try:
        v = float(value)
        if v >= 1_000_000:
            return f"R$ {v/1_000_000:.2f}M"
        return f"R$ {v:,.0f}"
    except Exception:
        return "-"

def _build_pdf(project, terrain, topo, imp, fin, resumo: str, project_data: dict) -> str:
    from fpdf import FPDF

    DARK    = (13, 15, 26)
    ACCENT  = (79, 195, 247)
    ACCENT2 = (124, 77, 255)
    WHITE   = (255, 255, 255)
    GRAY    = (159, 168, 218)
    LIGHT   = (232, 234, 246)
    SUCCESS = (76, 175, 80)
    MID     = (21, 24, 40)

    class PDF(FPDF):
        def header(self):
            self.set_fill_color(*ACCENT)
            self.rect(0, 0, 210, 3, "F")

        def footer(self):
            self.set_y(-14)
            self.set_fill_color(*MID)
            self.rect(0, self.get_y() - 1, 210, 16, "F")
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*GRAY)
            self.cell(0, 10, f"STOA Civil  |  Pagina {self.page_no()}  |  Gerado em {datetime.date.today().strftime('%d/%m/%Y')}", align="C")

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── COVER PAGE ──
    pdf.add_page()
    pdf.set_margins(0, 0, 0)

    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, 210, 3, "F")

    pdf.set_xy(20, 60)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 14, "STOA", ln=True)

    pdf.set_xy(20, 74)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 8, "Civil - Desenvolvimento Imobiliario com IA", ln=True)

    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(20, 92, 190, 92)

    pdf.set_xy(20, 100)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*LIGHT)
    pdf.multi_cell(170, 10, _safe(project.name))

    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 8, _safe(project.typology or "Empreendimento Imobiliario"), ln=True)

    f = project_data.get("financeiro") or {}
    metrics = []
    if terrain and terrain.area_ha:
        metrics.append(("Area Total", f"{terrain.area_ha:.1f} ha"))
    if imp and imp.num_lotes:
        metrics.append(("Lotes / Unidades", str(imp.num_lotes)))
    if f.get("vgv"):
        metrics.append(("VGV Estimado", _fmt_brl(f["vgv"])))
    if f.get("margem_bruta"):
        metrics.append(("Margem Bruta", f"{f['margem_bruta']:.1f}%"))

    for i, (label, value) in enumerate(metrics):
        x = 20 + (i % 2) * 90
        y = 160 + (i // 2) * 30
        pdf.set_xy(x, y)
        pdf.set_fill_color(*MID)
        pdf.rect(x, y, 80, 26, "F")
        pdf.set_draw_color(*ACCENT)
        pdf.rect(x, y, 80, 26, "D")
        pdf.set_xy(x + 4, y + 4)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*ACCENT)
        pdf.cell(72, 7, _safe(value))
        pdf.set_xy(x + 4, y + 13)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRAY)
        pdf.cell(72, 5, _safe(label).upper())

    pdf.set_xy(130, 270)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(60, 6, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}", align="R")

    # ── CONTENT PAGES ──
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    def section_header(title: str, color=ACCENT):
        pdf.set_fill_color(*color)
        pdf.rect(15, pdf.get_y(), 180, 9, "F")
        pdf.set_x(15)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*DARK)
        pdf.cell(180, 9, f"  {_safe(title)}", ln=True)
        pdf.set_text_color(40, 40, 40)
        pdf.ln(3)

    def data_row(label: str, value: str, shade=False):
        pdf.set_x(15)
        if shade:
            pdf.set_fill_color(240, 242, 250)
            pdf.rect(15, pdf.get_y(), 180, 7, "F")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(80, 80, 100)
        pdf.cell(75, 7, _safe(label), border="B")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(20, 20, 40)
        pdf.cell(105, 7, _safe(value), border="B", ln=True)

    def table_row(cells: list, header=False, widths=None):
        if widths is None:
            w = 180 // len(cells)
            widths = [w] * len(cells)
        pdf.set_x(15)
        for cell, width in zip(cells, widths):
            if header:
                pdf.set_fill_color(*MID)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*ACCENT)
                pdf.cell(width, 8, _safe(cell), border=1, fill=True, align="C")
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(20, 20, 40)
                pdf.cell(width, 7, _safe(cell), border=1, align="C")
        pdf.ln()

    section_header("1. Resumo Executivo", ACCENT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    pdf.set_x(15)
    pdf.multi_cell(180, 6, _safe(resumo))
    pdf.ln(6)

    if terrain:
        section_header("2. Dados do Terreno", ACCENT2)
        data_row("Endereco",     terrain.address or "-")
        data_row("Municipio/UF", f"{terrain.city or '-'} / {terrain.state or '-'}", shade=True)
        area_str = f"{terrain.area_ha:.2f} ha"
        if terrain.area_m2:
            area_str += f" ({terrain.area_m2:,.0f} m2)"
        data_row("Area Total",   area_str)
        data_row("Topografia",   terrain.topografia or "-", shade=True)
        data_row("Vegetacao",    terrain.vegetacao or "-")
        data_row("Acesso",       terrain.acesso or "-", shade=True)
        data_row("Zoneamento",   terrain.zoneamento or "-")
        pdf.ln(6)

    if topo:
        section_header("3. Analise Topografica", (79, 174, 110))
        data_row("Altitude Min/Max",   f"{topo.alt_min or '-'} m / {topo.alt_max or '-'} m")
        data_row("Desnivel Total",     f"{topo.desnivel or '-'} m", shade=True)
        data_row("Declividade Media",  f"{topo.decl_media or '-'}%")
        data_row("Declividade Maxima", f"{topo.decl_max or '-'}%", shade=True)
        data_row("Orientacao",         topo.orientacao_predominante or "-")
        if topo.area_util_m2:
            pct = round(topo.area_util_m2 / terrain.area_m2 * 100) if terrain and terrain.area_m2 else 0
            data_row("Area Util", f"{topo.area_util_m2:,.0f} m2 ({pct}%)", shade=True)
        pdf.ln(6)

    if imp:
        section_header("4. Implantacao Selecionada", (245, 127, 23))
        data_row("Alternativa",         imp.nome or "-")
        data_row("Numero de Lotes",     str(imp.num_lotes or "-"), shade=True)
        data_row("Area Media por Lote", f"{imp.area_media_lote or 0:.0f} m2")
        if imp.area_construida_total:
            data_row("Area Construida", f"{imp.area_construida_total:,.0f} m2", shade=True)
        if imp.area_verde:
            data_row("Area Verde",      f"{imp.area_verde:,.0f} m2")
        if imp.score_total:
            data_row("Score Total",     f"{imp.score_total}/10", shade=True)
        if imp.justificativa:
            pdf.ln(3)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(80, 80, 100)
            pdf.set_x(15)
            pdf.multi_cell(180, 5, _safe(imp.justificativa))
        pdf.ln(6)

    if fin and project_data.get("financeiro"):
        fdata = project_data["financeiro"]
        section_header("5. Viabilidade Financeira", SUCCESS)
        table_row(["Indicador", "Valor", "Referencia"], header=True, widths=[80, 50, 50])
        kpi_rows = [
            ("VGV Total",    _fmt_brl(fdata.get("vgv")),             "Receita bruta"),
            ("Lucro Bruto",  _fmt_brl(fdata.get("lucro_bruto")),     "Resultado"),
            ("Margem Bruta", f"{fdata.get('margem_bruta', 0):.1f}%", ">20% bom"),
            ("ROI",          f"{fdata.get('roi', 0):.1f}%",          ">15% atrativo"),
            ("Payback",      f"{fdata.get('payback_meses', 0)} meses", "Retorno invest."),
        ]
        for r in kpi_rows:
            table_row(list(r), widths=[80, 50, 50])

        # fin.cenarios ja e um dict real (coluna JSON populada direto em financial.py) --
        # nao precisa (e nao deve) ser extraido de analise_ia.
        cenarios = fin.cenarios or {}
        if cenarios:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*MID)
            pdf.set_x(15)
            pdf.cell(180, 6, "Analise de Cenarios:", ln=True)
            table_row(["Cenario", "VGV", "Margem"], header=True, widths=[60, 60, 60])
            for c_name in ["pessimista", "base", "otimista"]:
                c = cenarios.get(c_name, {})
                table_row([c_name.capitalize(), _fmt_brl(c.get("vgv")), f"{c.get('margem', '-')}%"], widths=[60, 60, 60])

        # analise_ia guarda {"recomendacoes_financeiras": [...], "alertas": [...]} como
        # JSON valido (ver backend/routers/financial.py). Antes era str(lista python),
        # o que quebrava o json.loads e zerava essa secao inteira -- corrigido.
        fin_ia = {}
        if fin.analise_ia:
            try:
                fin_ia = json.loads(fin.analise_ia) if isinstance(fin.analise_ia, str) else fin.analise_ia
            except Exception:
                fin_ia = {}

        recs = fin_ia.get("recomendacoes_financeiras", [])
        if recs:
            pdf.ln(6)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*MID)
            pdf.set_x(15)
            pdf.cell(0, 6, "Recomendacoes Financeiras:", ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 60)
            for r in recs[:5]:
                pdf.set_x(15)
                pdf.cell(5, 6, "->")
                pdf.multi_cell(175, 6, _safe(str(r)))

        alertas = fin_ia.get("alertas", [])
        if alertas:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(200, 80, 40)
            pdf.set_x(15)
            pdf.cell(0, 6, "Alertas:", ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 60)
            for a in alertas[:5]:
                pdf.set_x(15)
                pdf.cell(5, 6, "!")
                pdf.multi_cell(175, 6, _safe(str(a)))
        pdf.ln(4)

    pdf.ln(10)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRAY)
    pdf.set_x(15)
    pdf.cell(0, 5, "Este relatorio foi gerado automaticamente pelo STOA Civil com suporte de Inteligencia Artificial.", ln=True)
    pdf.set_x(15)
    pdf.cell(0, 5, "Os valores sao estimativas baseadas em dados de mercado e devem ser validados por profissionais habilitados.", ln=True)

    pdf_bytes = pdf.output()
    return base64.b64encode(bytes(pdf_bytes)).decode()
