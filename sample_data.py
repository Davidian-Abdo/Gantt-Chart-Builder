"""
sample_data.py
──────────────
Realistic bilingual (French / English) construction schedule for a
G+4 residential reinforced-concrete building with 2 basement levels.

Project:   Résidence Les Acacias — R+4 + 2 Sous-Sols
           Acacia Residences — G+4 + 2 Basement Levels
Structure: RC frame with hollow-core slab (plancher à corps creux)
Zones:     A (north wing) and B (south wing)
Duration:  ~18 months  (March 2024 → September 2025)
Tasks:     ~185 tasks across 7 disciplines
"""

import pandas as pd

# ──────────────────────────────────────────────────────────────────
# Project metadata  (used in the Streamlit UI banner)
# ──────────────────────────────────────────────────────────────────
PROJECT_META = {
    "name": "Résidence Les Acacias — R+4 + 2 Sous-Sols  /  Acacia Residences — G+4 + 2 Basements",
    "client": "Promoteur Exemple / Sample Developer",
    "location": "Zone Urbaine / Urban Zone",
    "start": "2024-03-04",
    "end_approx": "2025-09-30",
    "description": (
        "Bâtiment résidentiel R+4 avec 2 niveaux de sous-sol, structure en béton armé, "
        "plancher à corps creux, 2 zones de construction (Aile Nord A / Aile Sud B).\n"
        "G+4 residential RC-frame building with 2 basement levels, hollow-core composite "
        "slabs, 2 construction zones (North Wing A / South Wing B)."
    ),
}

# ──────────────────────────────────────────────────────────────────
# Discipline colour palette  (overrides app defaults for new entries)
# ──────────────────────────────────────────────────────────────────
SAMPLE_DISCIPLINE_COLORS = {
    "Préliminaires": "#FF6B6B",
    "Terrassement":  "#4ECDC4",
    "Fondations":    "#45B7D1",
    "GrosOeuvres":   "#96CEB4",
    "SecondOeuvres": "#FECA57",
    "Finitions":     "#E17055",
    "VRD":           "#A29BFE",
}


# ──────────────────────────────────────────────────────────────────
# Schedule builder
# ──────────────────────────────────────────────────────────────────
def get_sample_project() -> pd.DataFrame:
    """
    Build and return the full schedule DataFrame.
    Columns: TaskID | Discipline | TaskName | Zone | floor | Start | End
    """

    BASE = "2024-03-04"   # Monday — project kick-off

    rows: list[dict] = []

    def dt(offset_days: int) -> str:
        """Return BASE + offset_days as YYYY-MM-DD string."""
        return (pd.Timestamp(BASE) + pd.Timedelta(days=offset_days)).strftime("%Y-%m-%d")

    def task(
        task_id: str,
        discipline: str,
        task_name: str,
        zone: str,
        floor: int,
        start_offset: int,
        duration: int,
    ) -> None:
        rows.append(
            {
                "TaskID":     task_id,
                "Discipline": discipline,
                "TaskName":   task_name,
                "Zone":       zone,
                "floor":      floor,
                "Start":      dt(start_offset),
                "End":        dt(start_offset + max(duration, 1)),
            }
        )

    # ════════════════════════════════════════════════════════════════
    # 1 · PRÉLIMINAIRES / PRELIMINARY WORKS          (Days 0 – 14)
    # ════════════════════════════════════════════════════════════════
    prelim = [
        ("1.1_SITE", "Installation de chantier / Site Establishment & Mobilisation",             0,  6),
        ("1.2_SITE", "Clôture provisoire du chantier / Temporary Site Hoarding & Fencing",       0,  4),
        ("1.3_SITE", "Raccordements provisoires eau & élec. / Temporary Water & Power Supply",   2,  5),
        ("1.4_SITE", "Levé topographique et implantation / Topographic Survey & Setting Out",    4,  3),
        ("1.5_SITE", "Débroussaillage et nettoyage / Site Clearance & Demolition",               3,  5),
        ("1.6_SITE", "Plan d'implantation et piquetage / Structural Grid Layout & Pegging",      7,  2),
    ]
    for tid, name, s, dur in prelim:
        task(tid, "Préliminaires", name, "SITE", 0, s, dur)

    # ════════════════════════════════════════════════════════════════
    # 2 · TERRASSEMENT / EARTHWORKS                  (Days 8 – 38)
    # ════════════════════════════════════════════════════════════════
    earthwork_tasks = [
        ("2.1", "Décapage de la terre végétale / Topsoil Stripping & Stockpiling",               0,  3),
        ("2.2", "Terrassement général en grande masse / Bulk Excavation to Formation Level",      3, 10),
        ("2.3", "Fouilles en rigoles pour fondations / Trench Excavation for Foundations",       11,  6),
        ("2.4", "Blindage et soutènement des fouilles / Trench Shoring & Lateral Earth Support", 11,  8),
        ("2.5", "Épuisement et pompage des eaux / Groundwater Pumping & Dewatering",              3, 16),
        ("2.6", "Évacuation et mise en décharge / Spoil Removal & Licensed Off-Site Disposal",   3, 16),
    ]
    for zone, base in [("A", 8), ("B", 15)]:
        for seq, name, s, dur in earthwork_tasks:
            task(f"{seq}_TERR_{zone}", "Terrassement", name, zone, -2, base + s, dur)

    # ════════════════════════════════════════════════════════════════
    # 3 · FONDATIONS / FOUNDATIONS   F-2             (Days 30 – 62)
    # ════════════════════════════════════════════════════════════════
    foundation_tasks = [
        ("3.1", "Béton de propreté / Blinding Concrete Layer",                                    0,  2),
        ("3.2", "Ferraillage des semelles isolées / Isolated Pad Footing Reinforcement",           2,  7),
        ("3.3", "Coffrage des semelles / Footing Formwork Assembly",                               6,  4),
        ("3.4", "Coulage béton semelles / Pad Footing Reinforced Concrete Pour",                  10,  2),
        ("3.5", "Décoffrage et cure des semelles / Footing Stripping & Wet Curing",               13,  2),
        ("3.6", "Ferraillage des longrines / Ground Beam Cage Fabrication & Placement",           14,  6),
        ("3.7", "Coffrage des longrines / Ground Beam Formwork",                                  18,  3),
        ("3.8", "Coulage des longrines / Ground Beam Concrete Pour & Vibration",                  21,  2),
        ("3.9", "Remblaiement sous dallage / Sub-Slab Granular Fill & Compaction",                24,  4),
    ]
    for zone, base in [("A", 30), ("B", 38)]:
        for seq, name, s, dur in foundation_tasks:
            task(f"{seq}_F-2_{zone}", "Fondations", name, zone, -2, base + s, dur)

    # ════════════════════════════════════════════════════════════════
    # 4 · GROS ŒUVRES / STRUCTURAL WORKS   F-2 → F4  (Days 60 – 215)
    # ════════════════════════════════════════════════════════════════
    # Each floor: ~21-day cycle per zone.  Zone B starts 7 days after Zone A.
    structural_tasks = [
        ("4.1", "Ferraillage des poteaux et voiles BA / Column & Shear-Wall Cage Fixing",        0,  5),
        ("4.2", "Coffrage des poteaux et voiles / Column & Wall Formwork Assembly",               4,  4),
        ("4.3", "Coulage béton poteaux et voiles / Column & Wall Concrete Pour & Curing",         8,  2),
        ("4.4", "Décoffrage poteaux et voiles / Column & Wall Stripping",                        11,  2),
        ("4.5", "Coffrage plancher haut (poutres + dalle) / Upper Slab Formwork & Propping",     10,  5),
        ("4.6", "Pose des corps creux hourdis / Hollow-Core Block (Hourdis) Installation",       13,  3),
        ("4.7", "Ferraillage du plancher haut / Upper Slab & Beam Reinforcement Placement",      14,  4),
        ("4.8", "Réservations et fourreaux / Slab Penetrations, Sleeves & Blockouts",            15,  2),
        ("4.9", "Coulage plancher haut / Upper Slab Concrete Pour & Vibration",                  18,  1),
        ("4.10","Décoffrage plancher et étaiement / Slab Stripping & Early Back-Propping",       26,  2),
    ]

    # Floor label → (floor int, zone-A base day)
    floors = [
        ("F-2", -2,  60),
        ("F-1", -1,  81),
        ("F0",   0, 102),
        ("F1",   1, 123),
        ("F2",   2, 144),
        ("F3",   3, 165),
        ("F4",   4, 186),
    ]

    for flabel, fnum, base_A in floors:
        for zone, zone_offset in [("A", 0), ("B", 7)]:
            base = base_A + zone_offset
            for seq, name, s, dur in structural_tasks:
                task(f"{seq}_{flabel}_{zone}", "GrosOeuvres", name, zone, fnum, base + s, dur)

    # ════════════════════════════════════════════════════════════════
    # 5 · SECOND ŒUVRES / SECONDARY WORKS  F-1 → F4  (Days 190 – 320)
    # ════════════════════════════════════════════════════════════════
    # Secondary works follow ~2 floors behind structural works.
    secondary_tasks = [
        ("5.1",  "Maçonnerie des cloisons intérieures / Interior Partition Wall Blockwork",        0, 10),
        ("5.2",  "Plomberie brute (attentes, colonnes montantes) / Rough-In Plumbing & Risers",    5,  9),
        ("5.3",  "Électricité brute (conduits, boites) / Rough-In Electrical Conduits & Boxes",   5,  9),
        ("5.4",  "Gaines CVC et VMC / HVAC & Mechanical Ventilation Ductwork",                   10,  8),
        ("5.5",  "Enduits intérieurs gobetis + dressage / Plaster Scratch Coat & Dub-Out",        16, 12),
        ("5.6",  "Chape flottante sur isolant / Floating Floor Screed on Insulation",              24,  6),
        ("5.7",  "Étanchéité terrasses et balcons / Terrace & Balcony Waterproofing System",      18,  5),
    ]

    so_floors = [
        ("F-1", -1, 190),
        ("F0",   0, 210),
        ("F1",   1, 228),
        ("F2",   2, 246),
        ("F3",   3, 264),
        ("F4",   4, 282),
    ]

    for flabel, fnum, base in so_floors:
        for seq, name, s, dur in secondary_tasks:
            task(f"{seq}_{flabel}", "SecondOeuvres", name, "AB", fnum, base + s, dur)

    # ════════════════════════════════════════════════════════════════
    # 6 · FINITIONS / FINISHING WORKS  F0 → F4        (Days 290 – 430)
    # ════════════════════════════════════════════════════════════════
    finishing_tasks = [
        ("6.1",  "Carrelage sol et plinthes / Floor Tiling & Skirting",                           0, 10),
        ("6.2",  "Faïence salles de bains et cuisines / Bathroom & Kitchen Wall Tiling",           5,  9),
        ("6.3",  "Menuiseries extérieures (fenêtres, portes-fenêtres) / External Windows & Doors", 8, 10),
        ("6.4",  "Menuiseries intérieures (portes, boiseries) / Interior Doors, Frames & Joinery",14,  8),
        ("6.5",  "Peinture intérieure et finitions / Interior Painting & Decorative Finishes",     20, 12),
        ("6.6",  "Faux plafonds modulaires et suspentés / Modular & Suspended Ceiling Systems",   18,  8),
        ("6.7",  "Appareillage électrique final / Final Electrical Accessories & Light Fittings",  28,  5),
        ("6.8",  "Appareillage sanitaire (WC, lavabos, douches) / Sanitaryware & Plumbing Fixtures",30, 5),
        ("6.9",  "Revêtement de façade et isolation (ITE) / External Render & External Wall Insulation", 6, 18),
        ("6.10", "Nettoyage de fin de chantier et levée de réserves / Final Clean & Snagging",    35,  5),
    ]

    fin_floors = [
        ("F0",  0, 295),
        ("F1",  1, 313),
        ("F2",  2, 331),
        ("F3",  3, 349),
        ("F4",  4, 367),
    ]

    for flabel, fnum, base in fin_floors:
        for seq, name, s, dur in finishing_tasks:
            task(f"{seq}_{flabel}_FIN", "Finitions", name, "AB", fnum, base + s, dur)

    # ════════════════════════════════════════════════════════════════
    # 7 · VRD / SITE UTILITIES & EXTERNAL WORKS       (Days 330 – 410)
    # ════════════════════════════════════════════════════════════════
    vrd_base = 330
    vrd_tasks = [
        ("7.1_VRD",  "VRD", "Réseau assainissement EU (eaux usées) / Foul Water Drainage & Manhole Construction",    "EXT", 0,  0, 12),
        ("7.2_VRD",  "VRD", "Réseau assainissement EP (eaux pluviales) / Stormwater Drainage & Soakaway",            "EXT", 0,  5, 10),
        ("7.3_VRD",  "VRD", "Réseau d'eau potable et compteurs / Potable Water Supply Mains & Metering",             "EXT", 0,  8,  8),
        ("7.4_VRD",  "VRD", "Réseau électrique BT et coffrets / LV Electrical Distribution & Sub-Boards",           "EXT", 0, 12,  8),
        ("7.5_VRD",  "VRD", "Réseau gaz naturel / Natural Gas Supply Pipework & Pressure Testing",                   "EXT", 0, 10,  7),
        ("7.6_VRD",  "VRD", "Voirie interne et parkings (fondations) / Road Base & Car Park Sub-Base Construction",  "EXT", 0, 22, 10),
        ("7.7_VRD",  "VRD", "Revêtement bitumineux voirie / Bituminous Road Surfacing & Line Marking",               "EXT", 0, 32,  6),
        ("7.8_VRD",  "VRD", "Clôture définitive et portail automatique / Permanent Boundary Wall, Gates & Intercom", "EXT", 0, 35,  8),
        ("7.9_VRD",  "VRD", "Aménagements paysagers et espaces verts / Landscaping, Planting & Soft Works",          "EXT", 0, 42, 10),
        ("7.10_VRD", "VRD", "Éclairage extérieur décoratif et sécurité / External Decorative & Security Lighting",   "EXT", 0, 45,  5),
    ]
    for tid, disc, name, zone, fnum, s, dur in vrd_tasks:
        task(tid, disc, name, zone, fnum, vrd_base + s, dur)

    df = pd.DataFrame(rows)

    # ── Sanity-check: drop any row where Start >= End after date conversion ──
    df["_start"] = pd.to_datetime(df["Start"])
    df["_end"]   = pd.to_datetime(df["End"])
    df = df[df["_end"] > df["_start"]].drop(columns=["_start", "_end"]).reset_index(drop=True)

    return df