"""The list of real documents in the knowledge base. Every URL here was
live-verified (HTTP 200, content-type application/pdf) before being added —
see ARCHITECTURE.md for the verification log. To add a new document: add
one entry here and re-run `download_and_ingest.py`. No application code
changes needed.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ManifestEntry:
    title: str
    organization: str
    document_type: str
    source_url: str
    subfolder: str
    filename: str
    publication_date: date | None = None
    region: str | None = None


MANIFEST: list[ManifestEntry] = [
    ManifestEntry(
        title="EOP-011-4 — Emergency Operations",
        organization="NERC",
        document_type="reliability_standard",
        source_url="https://www.nerc.com/globalassets/standards/reliability-standards/eop/eop-011-4.pdf",
        subfolder="reliability",
        filename="nerc-eop-011-4-emergency-operations.pdf",
        region="North America",
    ),
    ManifestEntry(
        title="Business Practice Manual for Reliability Requirements",
        organization="CAISO",
        document_type="business_practice_manual",
        source_url="https://www.caiso.com/documents/business-practice-manual-for-reliability-requirements-version-dame.pdf",
        subfolder="operating_procedures",
        filename="caiso-bpm-reliability-requirements.pdf",
        region="California",
    ),
    ManifestEntry(
        title="2025 Annual Assessment of Demand Response and Advanced Metering",
        organization="FERC",
        document_type="report",
        source_url="https://www.ferc.gov/sites/default/files/2025-12/25_Annual%20Assessment%20of%20Demand%20Response_1212.pdf",
        subfolder="regulations",
        filename="ferc-2025-demand-response-assessment.pdf",
        publication_date=date(2025, 12, 1),
        region="United States",
    ),
    ManifestEntry(
        title="What the Duck Curve Tells Us About Managing a Green Grid",
        organization="CAISO",
        document_type="fast_facts",
        source_url="https://www.caiso.com/documents/flexibleresourceshelprenewables_fastfacts.pdf",
        subfolder="renewable_energy",
        filename="caiso-duck-curve-fast-facts.pdf",
        region="California",
    ),
    ManifestEntry(
        title="2023 Resource Adequacy Report",
        organization="CPUC",
        document_type="regulatory_report",
        source_url="https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/resource-adequacy-homepage/2023-resource-adequacy-reportv2.pdf",
        subfolder="california",
        filename="cpuc-2023-resource-adequacy-report.pdf",
        region="California",
    ),
    ManifestEntry(
        title="2020 Summer Loads and Resources Assessment",
        organization="CAISO",
        document_type="report",
        source_url="https://www.caiso.com/Documents/2020SummerLoadsandResourcesAssessment.pdf",
        subfolder="forecasting",
        filename="caiso-2020-summer-loads-assessment.pdf",
        publication_date=date(2020, 5, 1),
        region="California",
    ),
    ManifestEntry(
        title="Public Safety Power Shutoff (PSPS) Program Fact Sheet",
        organization="CAISO",
        document_type="fast_facts",
        source_url="https://www.caiso.com/documents/PublicSafetyPowerShutoffProgram-FactSheet.pdf",
        subfolder="california",
        filename="caiso-psps-fact-sheet.pdf",
        region="California",
    ),
    ManifestEntry(
        title="Public Safety Power Shutoff Post-Event Report (January 2025)",
        organization="CPUC",
        document_type="regulatory_report",
        source_url="https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/safety-and-enforcement-division/reports/psps-post-event-reports/2025/r1812005pge1222025-psps-postevent-report02072025.pdf",
        subfolder="california",
        filename="cpuc-psps-post-event-report-2025-01.pdf",
        publication_date=date(2025, 2, 7),
        region="California",
    ),
    ManifestEntry(
        title="2025 IEPR California Energy Demand Forecast — LSE/BA Tables",
        organization="CEC",
        document_type="report",
        source_url="https://www.energy.ca.gov/sites/default/files/2026-02/2025_IEPR_California_Energy_Demand_Forecast_LSE-BA_Tables_and_RASS_Kick_Off_ada.pdf",
        subfolder="forecasting",
        filename="cec-2025-iepr-demand-forecast.pdf",
        publication_date=date(2026, 2, 1),
        region="California",
    ),
    ManifestEntry(
        title="Joint Agency Reliability Planning Assessment",
        organization="CEC",
        document_type="regulatory_report",
        source_url="https://efiling.energy.ca.gov/GetDocument.aspx?tn=270009&DocumentContentId=107161",
        subfolder="california",
        filename="cec-joint-agency-reliability-planning-assessment.pdf",
        region="California",
    ),
    ManifestEntry(
        title="Business Practice Manual for Outage Management",
        organization="CAISO",
        document_type="business_practice_manual",
        source_url="https://bpmcm.caiso.com/BPM%20Document%20Library/Outage%20Management/Outage_Management_V6.pdf",
        subfolder="operating_procedures",
        filename="caiso-bpm-outage-management.pdf",
        region="California",
    ),
    ManifestEntry(
        title="TOP-001-5 — Transmission Operations",
        organization="NERC",
        document_type="reliability_standard",
        source_url="https://www.nerc.com/globalassets/standards/projects/2018-03/top-001-5_clean_02272019.pdf",
        subfolder="reliability",
        filename="nerc-top-001-5-transmission-operations.pdf",
        region="North America",
    ),
]
