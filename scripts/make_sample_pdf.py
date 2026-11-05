"""
Creates two FICTIONAL sample health policy PDFs for testing the pipeline.
"Demo Health Shield", "Demo Care Plus" and "Sample Insurance Co." do not exist — replace with real
policy wordings downloaded from insurer websites for the actual project.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14, spaceBefore=14, spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=8, spaceAfter=3)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=13.5, spaceAfter=4)

CONTENT = [
    ("h1", "SECTION A - DEFINITIONS"),
    ("h2", "A.1 Hospital"),
    ("p", "Hospital means any institution established for in-patient care and day care treatment of illness and/or injuries which has been registered as a hospital with the local authorities and has at least 10 in-patient beds in towns having a population of less than 10 lakhs and at least 15 in-patient beds in all other places."),
    ("h2", "A.2 Pre-Existing Disease"),
    ("p", "Pre-Existing Disease means any condition, ailment, injury or disease that is diagnosed by a physician within 36 months prior to the date of commencement of the policy issued by the insurer, or for which medical advice or treatment was recommended by, or received from, a physician within 36 months prior to the effective date of the policy."),
    ("h2", "A.3 Sum Insured"),
    ("p", "Sum Insured means the pre-defined limit specified in the Policy Schedule, which represents the maximum total and cumulative liability for any and all claims made under the policy in respect of the insured person during the policy year."),
    ("h1", "SECTION B - COVERAGE"),
    ("h2", "B.1 In-patient Hospitalisation"),
    ("p", "The Company shall indemnify the medical expenses incurred for in-patient care where the insured person is hospitalised for a minimum period of 24 consecutive hours on the advice of a medical practitioner."),
    ("p", "Covered expenses include room rent, boarding and nursing expenses, intensive care unit charges, fees of surgeons, anaesthetists and consultants, cost of medicines, drugs, diagnostic tests, operation theatre charges and cost of implants."),
    ("h2", "B.2 Room Rent Limit"),
    ("p", "Room rent, boarding and nursing expenses are payable up to 1% of the Sum Insured per day. Intensive Care Unit charges are payable up to 2% of the Sum Insured per day."),
    ("p", "If the insured person occupies a room with a rent higher than the eligible limit, all associated medical expenses, except cost of medicines, implants and consumables, shall be payable in the same proportion as the eligible room rent bears to the actual room rent."),
    ("h2", "B.3 Pre and Post Hospitalisation"),
    ("p", "Medical expenses incurred up to 30 days before the date of admission and up to 60 days after the date of discharge are covered, provided the in-patient claim is admissible under the policy."),
    ("h2", "B.4 Day Care Procedures"),
    ("p", "Medical expenses for day care procedures which require less than 24 hours of hospitalisation due to technological advancement, such as cataract surgery, dialysis and chemotherapy, are covered up to the Sum Insured."),
    ("h2", "B.5 Co-payment"),
    ("p", "A co-payment of 20% shall apply on every admissible claim if the insured person is aged 61 years or above at the time of entry into the policy. No co-payment applies to insured persons who entered the policy below age 61."),
    ("h1", "SECTION C - WAITING PERIODS"),
    ("h2", "C.1 Initial Waiting Period"),
    ("p", "Expenses related to the treatment of any illness within 30 days from the first policy commencement date shall be excluded, except claims arising due to an accident. This waiting period does not apply on subsequent renewals without break."),
    ("h2", "Code-Excl01 Pre-Existing Diseases"),
    ("p", "Expenses related to the treatment of a pre-existing disease and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first policy with the insurer."),
    ("h2", "Code-Excl02 Specified Disease or Procedure Waiting Period"),
    ("p", "Expenses related to the treatment of the listed conditions, surgeries or treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the first policy with the insurer."),
    ("p", "The listed conditions include: cataract; benign prostatic hypertrophy; hernia of all types; joint replacement including knee and hip replacement unless necessitated by accident; surgery for varicose veins; gall bladder stones; kidney stones; sinusitis; tonsillectomy; and hysterectomy."),
    ("h1", "SECTION D - PERMANENT EXCLUSIONS"),
    ("h2", "Code-Excl03 Investigation and Evaluation"),
    ("p", "Expenses related to any admission primarily for diagnostics and evaluation purposes only are excluded. Any diagnostic expenses which are not related or not incidental to the current diagnosis and treatment are excluded."),
    ("h2", "Code-Excl04 Rest Cure and Rehabilitation"),
    ("p", "Expenses related to any admission primarily for enforced bed rest and not for receiving treatment are excluded. This also includes custodial care either at home or in a nursing facility for personal care such as help with activities of daily living."),
    ("h2", "Code-Excl06 Cosmetic or Plastic Surgery"),
    ("p", "Expenses for cosmetic or plastic surgery or any treatment to change appearance unless for reconstruction following an accident, burn or cancer, or as part of medically necessary treatment to remove a direct and immediate health risk to the insured, are excluded."),
    ("h2", "Code-Excl12 Refractive Error"),
    ("p", "Expenses related to the treatment for correction of eye sight due to refractive error less than 7.5 dioptres are excluded."),
    ("h1", "SECTION E - CLAIM PROCEDURE"),
    ("h2", "E.1 Cashless Claims"),
    ("p", "Cashless facility is available only at network hospitals. The insured person must inform the Company at least 48 hours before a planned hospitalisation and within 24 hours of an emergency hospitalisation."),
    ("h2", "E.2 Reimbursement Claims"),
    ("p", "For reimbursement claims, all documents including the claim form, discharge summary, original bills and investigation reports must be submitted within 30 days from the date of discharge."),
]


# A second fictional policy with different numbers and numbered headings,
# so compare_policies and multi-policy search can be tested.
CONTENT_2 = [
    ("h1", "PART 1 - KEY DEFINITIONS"),
    ("h2", "1.1 Pre-Existing Disease"),
    ("p", "Pre-Existing Disease means any condition, ailment or injury diagnosed by a physician, or for which medical advice or treatment was received, within 48 months prior to the first policy issued by the insurer."),
    ("h2", "1.2 Network Provider"),
    ("p", "Network Provider means hospitals enlisted by the insurer to provide medical services to an insured person on payment by a cashless facility."),
    ("h1", "PART 2 - WHAT IS COVERED"),
    ("h2", "2.1 Hospitalisation Expenses"),
    ("p", "We will pay for medical expenses for hospitalisation of the insured person for a minimum period of 24 hours, including room charges, ICU charges, doctor fees, medicines and diagnostic tests."),
    ("h2", "2.2 Room Category"),
    ("p", "Room rent is covered up to a Single Private Room. There is no capping on room rent in rupee terms. If a room category higher than Single Private Room is chosen, a proportionate deduction applies on associated medical expenses."),
    ("h2", "2.3 Ambulance Cover"),
    ("p", "Road ambulance expenses are covered up to Rs 2,000 per hospitalisation for transfer to the nearest hospital in an emergency."),
    ("h2", "2.4 Co-payment"),
    ("p", "A co-payment of 10% applies on all claims, irrespective of the age of the insured person."),
    ("h2", "2.5 Restoration of Sum Insured"),
    ("p", "If the Sum Insured is exhausted during the policy year, it will be restored once by 100% for subsequent unrelated illnesses in the same policy year."),
    ("h1", "PART 3 - WAITING PERIODS"),
    ("h2", "3.1 First 30 Days"),
    ("p", "Any illness contracted within 30 days of the policy start date is not covered, except accidental injuries."),
    ("h2", "3.2 Pre-Existing Diseases"),
    ("p", "Pre-existing diseases are covered after 48 months of continuous coverage from the first policy start date."),
    ("h2", "3.3 Specified Illnesses and Surgeries"),
    ("p", "Treatment of cataract, hernia, kidney stones and gall bladder stones is covered after 24 months of continuous coverage. Joint replacement surgery including knee replacement is covered after 36 months of continuous coverage unless required due to an accident."),
    ("h2", "3.4 Maternity"),
    ("p", "Maternity expenses are not covered under this policy."),
    ("h1", "PART 4 - EXCLUSIONS"),
    ("h2", "4.1 Cosmetic Treatment"),
    ("p", "Cosmetic or aesthetic treatment of any description is excluded, unless required due to accident, burns or cancer."),
    ("h2", "4.2 Hazardous Sports"),
    ("p", "Expenses arising from participation in hazardous or adventure sports such as para-jumping, rock climbing, mountaineering and scuba diving are excluded."),
    ("h2", "4.3 Spectacles and Contact Lenses"),
    ("p", "Cost of spectacles, contact lenses and hearing aids is excluded."),
]

POLICIES = [
    ("demo_health_shield.pdf", "Demo Health Shield", "UIN: DEMO000TEST", CONTENT),
    ("demo_care_plus.pdf", "Demo Care Plus", "UIN: DEMO111TEST", CONTENT_2),
]


def build(filename, title, uin, content):
    out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "policies" / filename
    out.parent.mkdir(parents=True, exist_ok=True)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(40, A4[1] - 25, f"Sample Insurance Co. (fictional) | {title} | {uin}")
        canvas.drawRightString(A4[0] - 40, 20, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out), pagesize=A4, topMargin=50, bottomMargin=40, leftMargin=45, rightMargin=45)
    story = [Paragraph(f"{title} - Policy Wordings", ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=18, spaceAfter=12))]
    for kind, text in content:
        story.append(Paragraph(text, {"h1": H1, "h2": H2, "p": BODY}[kind]))
    story.append(Spacer(1, 6))
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Wrote {out}")


def main():
    for args in POLICIES:
        build(*args)


if __name__ == "__main__":
    main()
