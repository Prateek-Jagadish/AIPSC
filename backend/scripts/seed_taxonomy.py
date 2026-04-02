"""
scripts/seed_taxonomy.py
────────────────────────
Seeds the database with the complete UPSC topic taxonomy:
    Topics → Subtopics → Micro Tags

Run once after setting up the database:
    python scripts/seed_taxonomy.py

This gives the system its UPSC brain from Day 1.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionFactory, init_db
from app.models.topic import Topic, Subtopic, MicroTag, GSPaper, ExamFocus, CurrentAffairsSensitivity


# ── Taxonomy Data ─────────────────────────────────────────────────────────────
# Structure: (paper, topic_name, priority, exam_focus, subtopics)
# Each subtopic: (name, ca_sensitivity, priority, micro_tags)
# Each micro_tag: (name, pyq_weight, ca_weight, diagram_relevant)

TAXONOMY = [

    # ── GS2: POLITY ─────────────────────────────────────────────────────────
    (GSPaper.GS2, "Polity", 9.0, ExamFocus.BOTH, [
        ("Historical Underpinnings & Evolution", CurrentAffairsSensitivity.LOW, 6.0, [
            ("Regulating Act to Independence Act", 5.0, 3.0, False),
            ("Constituent Assembly", 7.0, 3.0, False),
            ("Objective Resolution", 6.0, 2.0, False),
        ]),
        ("Salient Features of the Constitution", CurrentAffairsSensitivity.MEDIUM, 8.0, [
            ("Federal vs Unitary Features", 8.0, 6.0, False),
            ("Parliamentary vs Presidential Form", 7.0, 5.0, False),
            ("Basic Structure Doctrine", 9.0, 7.0, False),
            ("Amendment Procedure", 8.0, 5.0, False),
        ]),
        ("Fundamental Rights, DPSP & Duties", CurrentAffairsSensitivity.HIGH, 9.0, [
            ("Right to Equality (Art 14–18)", 8.0, 7.0, False),
            ("Right to Freedom (Art 19–22)", 8.0, 7.0, False),
            ("Writs (Habeas Corpus, Mandamus...)", 8.0, 6.0, False),
            ("DPSP Categories", 7.0, 6.0, False),
            ("FR vs DPSP Conflict", 9.0, 7.0, False),
            ("Fundamental Duties", 6.0, 5.0, False),
        ]),
        ("Federalism & Centre-State Relations", CurrentAffairsSensitivity.HIGH, 9.5, [
            ("7th Schedule (Union/State/Concurrent)", 9.0, 7.0, False),
            ("Article 356 & President's Rule", 9.0, 8.0, False),
            ("Cooperative Federalism", 8.0, 9.0, False),
            ("GST Council", 8.0, 9.0, False),
            ("Finance Commission", 8.0, 7.0, False),
            ("Sarkaria & Punchhi Commission", 7.0, 5.0, False),
            ("Inter-State Water Disputes", 7.0, 8.0, True),
        ]),
        ("Parliament & State Legislatures", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("Money Bill vs Finance Bill", 9.0, 7.0, False),
            ("Zero Hour & Question Hour", 7.0, 6.0, False),
            ("Parliamentary Committees (PAC, Estimates...)", 7.0, 6.0, False),
            ("Anti-Defection Law (10th Schedule)", 8.0, 8.0, False),
            ("Rajya Sabha Special Powers", 7.0, 5.0, False),
        ]),
        ("The Judiciary", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("Collegium System", 9.0, 9.0, False),
            ("Judicial Review", 9.0, 7.0, False),
            ("PIL & Access to Justice", 8.0, 8.0, False),
            ("Judicial Activism vs Overreach", 8.0, 7.0, False),
            ("Curative Petition", 6.0, 5.0, False),
        ]),
        ("Constitutional Bodies", CurrentAffairsSensitivity.MEDIUM, 7.5, [
            ("Election Commission of India", 8.0, 8.0, False),
            ("CAG (Comptroller & Auditor General)", 7.0, 6.0, False),
            ("UPSC & State PSCs", 6.0, 5.0, False),
            ("Finance Commission", 8.0, 7.0, False),
        ]),
        ("Statutory & Regulatory Bodies", CurrentAffairsSensitivity.HIGH, 7.0, [
            ("NITI Aayog", 7.0, 8.0, False),
            ("Lokpal & Lokayukta", 7.0, 7.0, False),
            ("NHRC", 6.0, 6.0, False),
            ("CVC & CBI", 6.0, 7.0, False),
            ("SEBI, IRDAI, TRAI", 6.0, 7.0, False),
        ]),
        ("Electoral Reforms & Political Dynamics", CurrentAffairsSensitivity.HIGH, 8.0, [
            ("Electoral Bonds", 8.0, 9.0, False),
            ("Criminalization of Politics", 8.0, 8.0, False),
            ("Anti-Defection Law", 8.0, 8.0, False),
            ("State Funding of Elections", 7.0, 7.0, False),
            ("Role of Political Parties", 7.0, 6.0, False),
        ]),
    ]),

    # ── GS3: ECONOMY ────────────────────────────────────────────────────────
    (GSPaper.GS3, "Economy", 9.0, ExamFocus.BOTH, [
        ("Demand & Supply", CurrentAffairsSensitivity.HIGH, 8.0, [
            ("Law of Demand (exceptions & failures)", 7.0, 6.0, True),
            ("Law of Supply (short-run vs long-run)", 7.0, 6.0, True),
            ("Market Equilibrium & Disequilibrium", 8.0, 7.0, True),
            ("Elasticity (price, income, cross)", 8.0, 6.0, True),
            ("Government Intervention (tax, subsidy, price control)", 9.0, 9.0, True),
            ("Demand-Supply Shocks (inflation, oil, food)", 9.0, 9.0, True),
            ("Consumer & Producer Surplus", 6.0, 5.0, True),
        ]),
        ("Inflation", CurrentAffairsSensitivity.HIGH, 9.0, [
            ("Types of Inflation (demand-pull, cost-push)", 8.0, 9.0, False),
            ("WPI vs CPI", 8.0, 8.0, True),
            ("RBI Monetary Policy & Inflation Targeting", 9.0, 9.0, False),
            ("Food Inflation & MSP", 8.0, 9.0, False),
            ("Stagflation", 7.0, 7.0, False),
        ]),
        ("Banking & Financial System", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("RBI Functions & Monetary Tools", 9.0, 8.0, False),
            ("NPA & Bad Loans", 8.0, 8.0, False),
            ("Financial Inclusion (PMJDY, SFB)", 7.0, 8.0, False),
            ("Digital Payments & UPI", 7.0, 9.0, False),
            ("NBFC Regulation", 6.0, 7.0, False),
        ]),
        ("Fiscal Policy & Budget", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("Fiscal Deficit & FRBM Act", 9.0, 8.0, False),
            ("Direct vs Indirect Taxes", 8.0, 7.0, False),
            ("GST Structure & Impact", 8.0, 9.0, False),
            ("Subsidies (Food, Fertilizer, Fuel)", 8.0, 9.0, False),
            ("Public Debt Management", 7.0, 6.0, False),
        ]),
        ("Agriculture", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("MSP & Procurement", 9.0, 9.0, False),
            ("Agricultural Credit (KCC, NABARD)", 7.0, 8.0, False),
            ("Land Reforms", 7.0, 5.0, False),
            ("Food Security & PDS", 8.0, 8.0, False),
            ("Agri-tech & Digital Agriculture", 6.0, 8.0, False),
        ]),
    ]),

    # ── GS1: HISTORY ────────────────────────────────────────────────────────
    (GSPaper.GS1, "Ancient History", 7.0, ExamFocus.BOTH, [
        ("Indus Valley Civilization", CurrentAffairsSensitivity.MEDIUM, 8.0, [
            ("Town Planning & Drainage", 8.0, 5.0, True),
            ("Economy & Trade", 7.0, 4.0, False),
            ("Religion & Social Life", 6.0, 4.0, False),
            ("Major Sites (Harappa, Mohenjo-daro, Dholavira, Lothal)", 8.0, 5.0, True),
            ("Decline Theories", 7.0, 4.0, False),
            ("Seals, Script & Art", 7.0, 4.0, False),
        ]),
        ("Vedic Period", CurrentAffairsSensitivity.LOW, 6.0, [
            ("Early vs Later Vedic Society", 6.0, 3.0, False),
            ("Economy & Polity", 6.0, 3.0, False),
            ("Religion & Philosophy", 6.0, 3.0, False),
        ]),
    ]),

    # ── GS1: GEOGRAPHY ──────────────────────────────────────────────────────
    (GSPaper.GS1, "Geography", 8.0, ExamFocus.BOTH, [
        ("Physical Geography of India", CurrentAffairsSensitivity.MEDIUM, 8.0, [
            ("Himalayan Ranges & Rivers", 8.0, 6.0, True),
            ("Peninsular Rivers", 7.0, 7.0, True),
            ("Coastal Plains & Islands", 7.0, 6.0, True),
            ("Soil Types & Distribution", 7.0, 5.0, True),
        ]),
        ("Climate", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("Monsoon Mechanism", 9.0, 8.0, True),
            ("Climate Change Impacts on India", 9.0, 9.0, False),
            ("El Nino & La Nina", 8.0, 8.0, False),
            ("Cyclones & Disasters", 7.0, 9.0, True),
        ]),
    ]),

    # ── GS3: ENVIRONMENT ────────────────────────────────────────────────────
    (GSPaper.GS3, "Environment & Ecology", 9.0, ExamFocus.BOTH, [
        ("Biodiversity", CurrentAffairsSensitivity.HIGH, 9.0, [
            ("Protected Areas (Tiger Reserves, National Parks)", 8.0, 9.0, True),
            ("Western Ghats & Biodiversity Hotspots", 8.0, 8.0, True),
            ("IUCN Red List Categories", 7.0, 7.0, False),
            ("Invasive Species", 7.0, 8.0, False),
        ]),
        ("Climate Change & International Agreements", CurrentAffairsSensitivity.HIGH, 9.5, [
            ("Paris Agreement & NDCs", 9.0, 9.0, False),
            ("COP Conferences", 8.0, 9.0, False),
            ("IPCC Reports", 8.0, 8.0, False),
            ("India's Climate Commitments", 9.0, 9.0, False),
        ]),
    ]),

    # ── GS4: ETHICS ─────────────────────────────────────────────────────────
    (GSPaper.GS4, "Ethics, Integrity & Aptitude", 9.0, ExamFocus.MAINS, [
        ("Foundations of Ethics", CurrentAffairsSensitivity.LOW, 8.0, [
            ("Determinants of Ethics", 7.0, 3.0, False),
            ("Ethical Theories (Deontology, Consequentialism, Virtue)", 8.0, 3.0, False),
            ("Role of Family, Society in Shaping Ethics", 7.0, 3.0, False),
        ]),
        ("Attitude & Emotional Intelligence", CurrentAffairsSensitivity.LOW, 7.5, [
            ("Components of Attitude", 7.0, 3.0, False),
            ("Emotional Intelligence in Governance", 7.0, 4.0, False),
            ("Moral Intuition vs Moral Reasoning", 6.0, 3.0, False),
        ]),
        ("Public Service Values & Ethics in Governance", CurrentAffairsSensitivity.MEDIUM, 8.5, [
            ("Probity in Public Life", 8.0, 6.0, False),
            ("Codes of Ethics & Conduct", 7.0, 5.0, False),
            ("Whistleblower Protection", 7.0, 7.0, False),
            ("Conflict of Interest", 7.0, 6.0, False),
        ]),
        ("Case Studies", CurrentAffairsSensitivity.MEDIUM, 9.0, [
            ("Ethical Dilemmas in Civil Services", 9.0, 5.0, False),
            ("Stakeholder Analysis", 8.0, 5.0, False),
            ("Decision Making under Pressure", 8.0, 5.0, False),
        ]),
    ]),
    # ── GS1: ART & CULTURE ──────────────────────────────────────────────────
    (GSPaper.GS1, "Indian Heritage & Culture", 7.5, ExamFocus.BOTH, [
        ("Architecture & Sculpture", CurrentAffairsSensitivity.LOW, 8.0, [
            ("Temple Architecture", 8.0, 4.0, True),
            ("Cave Architecture", 7.0, 4.0, True),
        ]),
        ("Paintings & Performing Arts", CurrentAffairsSensitivity.LOW, 7.0, [
            ("Classical Dances", 7.0, 5.0, False),
            ("Mural & Miniature Paintings", 6.0, 3.0, False),
        ]),
    ]),

    # ── GS1: HISTORY (MODERN, MEDIEVAL, WORLD) ──────────────────────────────
    (GSPaper.GS1, "Medieval & Modern History", 8.5, ExamFocus.BOTH, [
        ("Mughal & Delhi Sultanate", CurrentAffairsSensitivity.LOW, 6.0, [
            ("Administration & Economy", 7.0, 3.0, False),
        ]),
        ("Freedom Struggle", CurrentAffairsSensitivity.LOW, 9.0, [
            ("Gandhian Phase", 9.0, 4.0, False),
            ("Revolutionary Movements", 8.0, 3.0, False),
        ]),
    ]),
    (GSPaper.GS1, "World History", 6.0, ExamFocus.MAINS, [
        ("Industrial Revolution & World Wars", CurrentAffairsSensitivity.LOW, 7.0, [
            ("World War I & II Causes", 8.0, 3.0, False),
        ]),
    ]),

    # ── GS1: INDIAN SOCIETY ─────────────────────────────────────────────────
    (GSPaper.GS1, "Indian Society & Social Issues", 8.0, ExamFocus.MAINS, [
        ("Women, Population & Globalization", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("Role of Women & Women's Organization", 9.0, 7.0, False),
            ("Effects of Globalization", 8.0, 8.0, False),
        ]),
    ]),

    # ── GS2: GOVERNANCE & SOCIAL JUSTICE ────────────────────────────────────
    (GSPaper.GS2, "Governance & Social Justice", 8.5, ExamFocus.MAINS, [
        ("Government Policies & Interventions", CurrentAffairsSensitivity.HIGH, 9.0, [
            ("Health & Education Sectors", 9.0, 9.0, False),
            ("Poverty & Hunger Issues", 9.0, 9.0, False),
        ]),
        ("E-Governance & Civil Services", CurrentAffairsSensitivity.MEDIUM, 8.0, [
            ("Role of Civil Services in a Democracy", 8.0, 5.0, False),
        ]),
    ]),

    # ── GS2: INTERNATIONAL RELATIONS ────────────────────────────────────────
    (GSPaper.GS2, "International Relations", 9.0, ExamFocus.BOTH, [
        ("India & Its Neighborhood", CurrentAffairsSensitivity.HIGH, 9.0, [
            ("Bilateral Relations (China, Pak, etc.)", 9.0, 9.0, True),
        ]),
        ("Global Groupings & Institutions", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("UN, WTO, World Bank", 8.0, 8.0, False),
            ("BRICS, Quad, SCO", 9.0, 9.0, True),
        ]),
    ]),

    # ── GS3: SCIENCE & TECHNOLOGY ───────────────────────────────────────────
    (GSPaper.GS3, "Science and Technology", 8.5, ExamFocus.BOTH, [
        ("Space, IT & Emerging Tech", CurrentAffairsSensitivity.HIGH, 9.0, [
            ("ISRO Missions", 9.0, 9.0, False),
            ("AI & Biotechnology", 8.0, 9.0, False),
        ]),
    ]),

    # ── GS3: INTERNAL SECURITY & DISASTER MANAGEMENT ────────────────────────
    (GSPaper.GS3, "Security & Disaster Management", 8.5, ExamFocus.MAINS, [
        ("Internal Security Challenges", CurrentAffairsSensitivity.HIGH, 8.5, [
            ("Extremism & Terrorism", 8.0, 8.0, True),
            ("Cyber Security", 9.0, 9.0, False),
        ]),
        ("Disaster Management", CurrentAffairsSensitivity.HIGH, 8.0, [
            ("NDMA Guidelines & Policies", 8.0, 8.0, False),
        ]),
    ]),

    # ── CSAT: PRELIMS GS PAPER 2 ────────────────────────────────────────────
    (GSPaper.PRELIMS_GS2, "CSAT - Aptitude & Reasoning", 8.5, ExamFocus.PRELIMS, [
        ("Comprehension & Communication", CurrentAffairsSensitivity.LOW, 8.0, [
            ("Reading Comprehension", 9.0, 1.0, False),
        ]),
        ("Logical Reasoning & Quant", CurrentAffairsSensitivity.LOW, 9.0, [
            ("Quantitative Aptitude", 9.0, 1.0, False),
            ("Logical & Analytical Reasoning", 8.0, 1.0, False),
        ]),
    ]),
]


# ── Seeder Function ───────────────────────────────────────────────────────────

async def seed(session: AsyncSession):
    print("\n🌱 Seeding UPSC Topic Taxonomy...\n")

    total_topics = total_subtopics = total_microtags = 0

    for paper, topic_name, topic_priority, topic_exam_focus, subtopic_data in TAXONOMY:

        # Create Topic
        topic = Topic(
            name=topic_name,
            paper=paper,
            priority_score=topic_priority,
            exam_focus=topic_exam_focus,
        )
        session.add(topic)
        await session.flush()   # get topic.id
        total_topics += 1
        print(f"  ✅ Topic: [{paper}] {topic_name}")

        for st_name, ca_sensitivity, st_priority, microtag_data in subtopic_data:

            # Create Subtopic
            subtopic = Subtopic(
                topic_id=topic.id,
                name=st_name,
                priority_score=st_priority,
                ca_sensitivity=ca_sensitivity,
            )
            session.add(subtopic)
            await session.flush()
            total_subtopics += 1

            for mt_name, pyq_w, ca_w, diagram in microtag_data:

                # Create MicroTag
                mt = MicroTag(
                    subtopic_id=subtopic.id,
                    name=mt_name,
                    pyq_weight=pyq_w,
                    current_affairs_weight=ca_w,
                    diagram_relevant=diagram,
                )
                session.add(mt)
                total_microtags += 1

    await session.commit()

    print(f"\n{'='*50}")
    print(f"  ✅ Taxonomy seeded successfully!")
    print(f"  📚 Topics:    {total_topics}")
    print(f"  📑 Subtopics: {total_subtopics}")
    print(f"  🏷️  MicroTags: {total_microtags}")
    print(f"{'='*50}\n")


async def main():
    await init_db()
    async with AsyncSessionFactory() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
