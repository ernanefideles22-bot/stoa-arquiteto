from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import base64, json, traceback
from ..models.database import get_db, Project, Terrain, Topography, Implantation, Financial
from ..services import ai_engine

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
        topo = db.query(Topography).filter(Topography.project_id == data.project_id).first()
        imp = db.query(Implantation).filter(Implantation.project_id == data.project_id).first()
        fin = db.query(Financial).filter(Financial.project_id == data.project_id).first()

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
        if fin:
            fin_ia = {}
            if fin.analise_ia:
                try:
                    fin_ia = json.loads(fin.analise_ia) if isinstance(fin.analise_ia, str) else fin.analise_ia
                except Exception:
                    fin_ia = {}
            project_data["financeiro"] = {
                "vgv": fin_ia.get("receitas", {}).get("vgv_total", 0),
                "lucro_bruto": fin_ia.get("resultado", {}).get("lucro_bruto", 0),
                "margem_bruta": fin_ia.get("resultado", {}).get("margem_bruta_percent", 0),
                "roi": fin_ia.get("resultado", {}).get("roi_percent", 0),
                "payback_meses": fin_ia.get("resultado", {}).get("payback_meses", 0),
            }

        # Generate AI executive summary
        resumo = ""
        resumo_error = None
        try:
            resumo = await ai_engine.gerar_resumo_executivo(project_data)
        except Exception as e:
            resumo_error = str(e)
            resumo = f"Resumo nao disponivel: {resumo_error}"

        # Generate PDF
        pdf_b64 = None
        pdf_error = None
        try:
            pdf_b64 = _build_pdf(project, terrain, imp, fin, resumo, project_data)
        except Exception as e:
            pdf_error = traceback.format_exc()

        return {
            "resumo_executivo": resumo,
            "pdf_base64": pdf_b64,
            "has_terrain": terrain is not None,
            "has_topo": topo is not None,
            "has_implantacao": imp is not None,
            "has_financeiro": fin is not None,
            "debug_resumo_error": resumo_error,
            "debug_pdf_error": pdf_error,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {traceback.format_exc()}")


def _build_pdf(project, terrain, imp, fin, resumo: str, project_data: dict) -> str:
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_fill_color(26, 35, 50)
            self.rect(0, 0, 210, 20, 'F')
            self.set_y(5)
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, "STOA CIVIL - Relatorio de Viabilidade", align="C")
            self.set_text_color(0, 0, 0)
            self.ln(16)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 8, f"Pagina {self.page_no()} - STOA Civil", align="C")

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 25, 15)

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(26, 35, 50)
    name_safe = project.name.encode('latin-1', errors='replace').decode('latin-1')
    pdf.cell(0, 10, name_safe, ln=True)
    pdf.ln(4)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 35, 50)
    pdf.cell(0, 8, "Resumo Executivo", ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    resumo_safe = resumo.encode('latin-1', errors='replace').decode('latin-1')
    pdf.multi_cell(0, 6, resumo_safe)
    pdf.ln(6)

    if terrain:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(26, 35, 50)
        pdf.cell(0, 8, "Dados do Terreno", ln=True)
        pdf.ln(2)
        _row(pdf, "Area", f"{terrain.area_ha:.2f} ha")
        _row(pdf, "Municipio", str(terrain.city or "-").encode('latin-1', errors='replace').decode('latin-1'))
        _row(pdf, "Zona de Uso", str(terrain.zoneamento or "-").encode('latin-1', errors='replace').decode('latin-1'))
        pdf.ln(4)

    if imp:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(26, 35, 50)
        pdf.cell(0, 8, "Implantacao", ln=True)
        pdf.ln(2)
        _row(pdf, "Numero de Lotes", str(imp.num_lotes or "-"))
        _row(pdf, "Area Media por Lote", f"{imp.area_media_lote or 0:.0f} m2")
        pdf.ln(4)

    if fin and project_data.get("financeiro"):
        f = project_data["financeiro"]
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(26, 35, 50)
        pdf.cell(0, 8, "Viabilidade Financeira", ln=True)
        pdf.ln(2)
        _row(pdf, "VGV Total", f"R$ {f['vgv']:,.0f}")
        _row(pdf, "Lucro Bruto", f"R$ {f['lucro_bruto']:,.0f}")
        _row(pdf, "Margem Bruta", f"{f['margem_bruta']:.1f}%")
        _row(pdf, "ROI", f"{f['roi']:.1f}%")
        _row(pdf, "Payback", f"{f['payback_meses']} meses")
        pdf.ln(4)

    pdf_bytes = pdf.output()
    return base64.b64encode(bytes(pdf_bytes)).decode()


def _row(pdf, label: str, value: str):
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(75, 7, label + ":", border="B")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 7, value, border="B", ln=True)
