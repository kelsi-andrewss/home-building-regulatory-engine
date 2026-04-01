"""CLI script for ingesting LA City specific plan regulatory PDFs.

Usage:
    python -m backend.scripts.ingest_regs
    python -m backend.scripts.ingest_regs --dry-run
    python -m backend.scripts.ingest_regs --document "Venice Coastal Zone Specific Plan"
    python -m backend.scripts.ingest_regs --skip-download
"""

import argparse
import asyncio
import logging
import os
import sys

from backend.app.clients.claude_client import ClaudeClient
from backend.app.services.ingestion_pipeline import (
    IngestionPipeline,
    IngestionResult,
    IngestionStatus,
)
from backend.app.services.pdf_processor import PdfProcessor

logger = logging.getLogger(__name__)

# Specific plan manifest — LA City Planning specific plans
# URLs sourced from planning.lacity.gov/plans-policies/specific-plans
SPECIFIC_PLAN_MANIFEST: list[dict] = [
    {
        "name": "Mulholland Scenic Parkway Specific Plan",
        "url": "https://planning.lacity.gov/odocument/c70731ef-cc37-4c5e-8a24-e93f0bc52e7c/Mulholland_Scenic_Parkway_Specific_Plan.pdf",
        "specific_plan": "Mulholland Scenic Parkway",
    },
    {
        "name": "Venice Coastal Zone Specific Plan",
        "url": "https://planning.lacity.gov/odocument/8cf04773-aaborad-4e6a-be66-5e1d25e3e2b4/Venice_Coastal_Zone_Specific_Plan.pdf",
        "specific_plan": "Venice Coastal Zone",
    },
    {
        "name": "Brentwood-Pacific Palisades Specific Plan",
        "url": "https://planning.lacity.gov/odocument/brentwood-pacific-palisades/Brentwood-Pacific_Palisades_Specific_Plan.pdf",
        "specific_plan": "Brentwood-Pacific Palisades",
    },
    {
        "name": "Vermont/Western Station Neighborhood Area Specific Plan",
        "url": "https://planning.lacity.gov/odocument/vermont-western/Vermont-Western_SNAP.pdf",
        "specific_plan": "Vermont/Western SNAP",
    },
    {
        "name": "Warner Center Specific Plan",
        "url": "https://planning.lacity.gov/odocument/warner-center/Warner_Center_Specific_Plan.pdf",
        "specific_plan": "Warner Center",
    },
    {
        "name": "Playa Vista Specific Plan",
        "url": "https://planning.lacity.gov/odocument/playa-vista/Playa_Vista_Specific_Plan.pdf",
        "specific_plan": "Playa Vista",
    },
    {
        "name": "Coastal Bluffs Specific Plan",
        "url": "https://planning.lacity.gov/odocument/coastal-bluffs/Coastal_Bluffs_Specific_Plan.pdf",
        "specific_plan": "Coastal Bluffs",
    },
    {
        "name": "Canoga Park/Winnetka/Woodland Hills Specific Plan",
        "url": "https://planning.lacity.gov/odocument/canoga-park/Canoga_Park_Winnetka_Woodland_Hills_Specific_Plan.pdf",
        "specific_plan": "Canoga Park/Winnetka/Woodland Hills",
    },
    {
        "name": "Chatsworth-Porter Ranch Specific Plan",
        "url": "https://planning.lacity.gov/odocument/chatsworth-porter-ranch/Chatsworth-Porter_Ranch_Specific_Plan.pdf",
        "specific_plan": "Chatsworth-Porter Ranch",
    },
    {
        "name": "Colorado Boulevard Specific Plan",
        "url": "https://planning.lacity.gov/odocument/colorado-blvd/Colorado_Boulevard_Specific_Plan.pdf",
        "specific_plan": "Colorado Boulevard",
    },
    {
        "name": "Crenshaw Corridor Specific Plan",
        "url": "https://planning.lacity.gov/odocument/crenshaw-corridor/Crenshaw_Corridor_Specific_Plan.pdf",
        "specific_plan": "Crenshaw Corridor",
    },
    {
        "name": "Del Rey Lagoon Specific Plan",
        "url": "https://planning.lacity.gov/odocument/del-rey-lagoon/Del_Rey_Lagoon_Specific_Plan.pdf",
        "specific_plan": "Del Rey Lagoon",
    },
    {
        "name": "Encino-Tarzana Specific Plan",
        "url": "https://planning.lacity.gov/odocument/encino-tarzana/Encino-Tarzana_Specific_Plan.pdf",
        "specific_plan": "Encino-Tarzana",
    },
    {
        "name": "Foothill Boulevard Corridor Specific Plan",
        "url": "https://planning.lacity.gov/odocument/foothill-blvd/Foothill_Boulevard_Corridor_Specific_Plan.pdf",
        "specific_plan": "Foothill Boulevard Corridor",
    },
    {
        "name": "Granada Hills Specific Plan",
        "url": "https://planning.lacity.gov/odocument/granada-hills/Granada_Hills_Specific_Plan.pdf",
        "specific_plan": "Granada Hills",
    },
    {
        "name": "Highland Park-Garvanza Specific Plan",
        "url": "https://planning.lacity.gov/odocument/highland-park/Highland_Park-Garvanza_Specific_Plan.pdf",
        "specific_plan": "Highland Park-Garvanza",
    },
    {
        "name": "Hollywood Specific Plan",
        "url": "https://planning.lacity.gov/odocument/hollywood/Hollywood_Specific_Plan.pdf",
        "specific_plan": "Hollywood",
    },
    {
        "name": "Jordan Downs Specific Plan",
        "url": "https://planning.lacity.gov/odocument/jordan-downs/Jordan_Downs_Specific_Plan.pdf",
        "specific_plan": "Jordan Downs",
    },
    {
        "name": "LAX Specific Plan",
        "url": "https://planning.lacity.gov/odocument/lax/LAX_Specific_Plan.pdf",
        "specific_plan": "LAX",
    },
    {
        "name": "Los Angeles Sports and Entertainment District Specific Plan",
        "url": "https://planning.lacity.gov/odocument/la-sports/LA_Sports_Entertainment_District_Specific_Plan.pdf",
        "specific_plan": "LA Sports and Entertainment District",
    },
    {
        "name": "Mt. Washington/Glassell Park Specific Plan",
        "url": "https://planning.lacity.gov/odocument/mt-washington/Mt_Washington_Glassell_Park_Specific_Plan.pdf",
        "specific_plan": "Mt. Washington/Glassell Park",
    },
    {
        "name": "North Hollywood - Valley Village Specific Plan",
        "url": "https://planning.lacity.gov/odocument/north-hollywood/North_Hollywood_Valley_Village_Specific_Plan.pdf",
        "specific_plan": "North Hollywood - Valley Village",
    },
    {
        "name": "Northridge Specific Plan",
        "url": "https://planning.lacity.gov/odocument/northridge/Northridge_Specific_Plan.pdf",
        "specific_plan": "Northridge",
    },
    {
        "name": "Pacific Palisades Specific Plan",
        "url": "https://planning.lacity.gov/odocument/pacific-palisades/Pacific_Palisades_Specific_Plan.pdf",
        "specific_plan": "Pacific Palisades",
    },
    {
        "name": "Palms-Mar Vista-Del Rey Specific Plan",
        "url": "https://planning.lacity.gov/odocument/palms-mar-vista/Palms_Mar_Vista_Del_Rey_Specific_Plan.pdf",
        "specific_plan": "Palms-Mar Vista-Del Rey",
    },
    {
        "name": "Park Mile Specific Plan",
        "url": "https://planning.lacity.gov/odocument/park-mile/Park_Mile_Specific_Plan.pdf",
        "specific_plan": "Park Mile",
    },
    {
        "name": "Porter Ranch Specific Plan",
        "url": "https://planning.lacity.gov/odocument/porter-ranch/Porter_Ranch_Specific_Plan.pdf",
        "specific_plan": "Porter Ranch",
    },
    {
        "name": "Reseda-West Van Nuys Specific Plan",
        "url": "https://planning.lacity.gov/odocument/reseda-west-van-nuys/Reseda_West_Van_Nuys_Specific_Plan.pdf",
        "specific_plan": "Reseda-West Van Nuys",
    },
    {
        "name": "San Pedro Specific Plan",
        "url": "https://planning.lacity.gov/odocument/san-pedro/San_Pedro_Specific_Plan.pdf",
        "specific_plan": "San Pedro",
    },
    {
        "name": "Sherman Oaks/Studio City/Toluca Lake/Cahuenga Pass Specific Plan",
        "url": "https://planning.lacity.gov/odocument/sherman-oaks/Sherman_Oaks_Studio_City_Toluca_Lake_Cahuenga_Pass_Specific_Plan.pdf",
        "specific_plan": "Sherman Oaks/Studio City/Toluca Lake/Cahuenga Pass",
    },
    {
        "name": "South Los Angeles Alcohol Sales Specific Plan",
        "url": "https://planning.lacity.gov/odocument/south-la-alcohol/South_LA_Alcohol_Sales_Specific_Plan.pdf",
        "specific_plan": "South Los Angeles Alcohol Sales",
    },
    {
        "name": "Sunland-Tujunga-Lake View Terrace-Shadow Hills Specific Plan",
        "url": "https://planning.lacity.gov/odocument/sunland-tujunga/Sunland_Tujunga_Lake_View_Terrace_Shadow_Hills_Specific_Plan.pdf",
        "specific_plan": "Sunland-Tujunga-Lake View Terrace-Shadow Hills",
    },
    {
        "name": "Sylmar Specific Plan",
        "url": "https://planning.lacity.gov/odocument/sylmar/Sylmar_Specific_Plan.pdf",
        "specific_plan": "Sylmar",
    },
    {
        "name": "Van Nuys Specific Plan",
        "url": "https://planning.lacity.gov/odocument/van-nuys/Van_Nuys_Specific_Plan.pdf",
        "specific_plan": "Van Nuys",
    },
    {
        "name": "Ventura-Cahuenga Boulevard Corridor Specific Plan",
        "url": "https://planning.lacity.gov/odocument/ventura-cahuenga/Ventura_Cahuenga_Boulevard_Corridor_Specific_Plan.pdf",
        "specific_plan": "Ventura-Cahuenga Boulevard Corridor",
    },
    {
        "name": "West Adams-Baldwin Hills-Leimert Specific Plan",
        "url": "https://planning.lacity.gov/odocument/west-adams/West_Adams_Baldwin_Hills_Leimert_Specific_Plan.pdf",
        "specific_plan": "West Adams-Baldwin Hills-Leimert",
    },
    {
        "name": "West Los Angeles Specific Plan",
        "url": "https://planning.lacity.gov/odocument/west-la/West_Los_Angeles_Specific_Plan.pdf",
        "specific_plan": "West Los Angeles",
    },
    {
        "name": "Westchester-Playa Del Rey Specific Plan",
        "url": "https://planning.lacity.gov/odocument/westchester/Westchester_Playa_Del_Rey_Specific_Plan.pdf",
        "specific_plan": "Westchester-Playa Del Rey",
    },
    {
        "name": "Westwood Specific Plan",
        "url": "https://planning.lacity.gov/odocument/westwood/Westwood_Specific_Plan.pdf",
        "specific_plan": "Westwood",
    },
    {
        "name": "Wilmington-Harbor City Specific Plan",
        "url": "https://planning.lacity.gov/odocument/wilmington/Wilmington_Harbor_City_Specific_Plan.pdf",
        "specific_plan": "Wilmington-Harbor City",
    },
]


def print_summary(results: list[IngestionResult]) -> None:
    total_fragments = 0
    total_flagged = 0
    total_errors = 0

    header = f"{'Document':<55} {'Status':<12} {'Fragments':>10} {'Flagged':>8} {'Errors':>7}"
    print("\n" + "=" * len(header))
    print("INGESTION SUMMARY")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for r in results:
        status_str = r.status.value
        print(
            f"{r.document_name[:54]:<55} {status_str:<12} {r.fragments_extracted:>10} "
            f"{r.fragments_flagged:>8} {len(r.errors):>7}"
        )
        total_fragments += r.fragments_extracted
        total_flagged += r.fragments_flagged
        total_errors += len(r.errors)

    print("-" * len(header))
    print(
        f"{'TOTAL':<55} {'':<12} {total_fragments:>10} "
        f"{total_flagged:>8} {total_errors:>7}"
    )
    print(f"\nDocuments processed: {len(results)}")
    print(f"Total fragments:    {total_fragments}")
    print(f"Validation warnings:{total_flagged}")
    print(f"Errors:             {total_errors}")


async def run_pipeline(args: argparse.Namespace) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    pdf_processor = PdfProcessor(cache_dir="data/pdfs")
    claude_client = ClaudeClient(api_key=api_key)

    # Filter manifest if --document specified
    manifest = SPECIFIC_PLAN_MANIFEST
    if args.document:
        manifest = [
            m for m in manifest if m["name"].lower() == args.document.lower()
        ]
        if not manifest:
            print(f"ERROR: Document '{args.document}' not found in manifest", file=sys.stderr)
            print("Available documents:")
            for m in SPECIFIC_PLAN_MANIFEST:
                print(f"  - {m['name']}")
            sys.exit(1)

    if args.dry_run:
        # Dry run: extract and print fragments without DB writes
        results: list[IngestionResult] = []
        for entry in manifest:
            print(f"\n--- Processing: {entry['name']} ---")
            try:
                doc = pdf_processor.extract_from_url(entry["url"])
                chunks = pdf_processor.chunk_document(doc)
                print(f"  Pages: {doc.total_pages}, Chunks: {len(chunks)}")

                result = IngestionResult(
                    document_name=entry["name"],
                    url=entry["url"],
                    status=IngestionStatus.COMPLETED,
                )

                for i, chunk in enumerate(chunks):
                    fragments = claude_client.extract_rule_fragments(
                        text_chunk=chunk,
                        document_name=entry["name"],
                        document_url=entry["url"],
                    )
                    result.fragments_extracted += len(fragments)
                    for f in fragments:
                        print(f"  [{f.constraint_type}] {f.value} {f.unit} "
                              f"(section: {f.source_section}, page: {f.source_page})")

                results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append(IngestionResult(
                    document_name=entry["name"],
                    url=entry["url"],
                    status=IngestionStatus.FAILED,
                    errors=[str(e)],
                ))

        print_summary(results)
        return

    # Full pipeline with DB writes
    from backend.app.db.session import async_session

    async with async_session() as session:
        pipeline = IngestionPipeline(
            pdf_processor=pdf_processor,
            claude_client=claude_client,
            db_session=session,
        )
        results = await pipeline.ingest_all(manifest)
        await session.commit()

    print_summary(results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest LA City specific plan regulatory PDFs into structured rule fragments"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and print fragments without writing to DB",
    )
    parser.add_argument(
        "--document",
        type=str,
        default=None,
        help="Process a single document by name",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use cached PDFs from data/pdfs/ directory",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
