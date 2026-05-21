"""
Sample 990 filing data (American Red Cross shape) for offline testing.
Figures are illustrative, not real financials.
"""

SAMPLE_ORG = {
    "ein": "530196605",
    "name": "AMERICAN RED CROSS (Demo)",
    "city": "Washington",
    "state": "DC",
    "ntee_code": "P20",
    "subsection_code": "3",
    "ruling": "194601",
}

SAMPLE_FILINGS = [
    {
        "tax_prd_yr": 2019,
        "totrevenue": 2_800_000_000,
        "totfuncexpns": 2_700_000_000,
        "totassetsend": 3_100_000_000,
        "totliabend": 1_200_000_000,
        "prgmservexpns": 2_100_000_000,
        "totmngmntservcs": 400_000_000,
        "totfunrndng": 200_000_000,
        "totcntrbgfts": 1_900_000_000,
        "compofcers": 12_000_000,
    },
    {
        "tax_prd_yr": 2020,
        "totrevenue": 3_100_000_000,
        "totfuncexpns": 2_900_000_000,
        "totassetsend": 3_400_000_000,
        "totliabend": 1_100_000_000,
        "prgmservexpns": 2_350_000_000,
        "totmngmntservcs": 380_000_000,
        "totfunrndng": 170_000_000,
        "totcntrbgfts": 2_200_000_000,
        "compofcers": 11_500_000,
    },
    {
        "tax_prd_yr": 2021,
        "totrevenue": 2_950_000_000,
        "totfuncexpns": 3_050_000_000,
        "totassetsend": 3_200_000_000,
        "totliabend": 1_300_000_000,
        "prgmservexpns": 2_400_000_000,
        "totmngmntservcs": 420_000_000,
        "totfunrndng": 230_000_000,
        "totcntrbgfts": 2_000_000_000,
        "compofcers": 12_800_000,
    },
    {
        "tax_prd_yr": 2022,
        "totrevenue": 3_250_000_000,
        "totfuncexpns": 3_100_000_000,
        "totassetsend": 3_500_000_000,
        "totliabend": 1_150_000_000,
        "prgmservexpns": 2_550_000_000,
        "totmngmntservcs": 360_000_000,
        "totfunrndng": 190_000_000,
        "totcntrbgfts": 2_300_000_000,
        "compofcers": 13_200_000,
    },
]
