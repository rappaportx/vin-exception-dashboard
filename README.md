# VIN Exception Dashboard - Ahmed Group

Real-time inventory reconciliation dashboard tracking vehicles across 4 data systems.

## Live Dashboard

**[View Dashboard](https://storage.googleapis.com/sonorous-key-320714-vin-dashboard/index.html)**

## Overview

| Metric | Value |
|--------|-------|
| **Total Vehicles Tracked** | 41,162 |
| **Data Sources** | 4 (CDK, vAuto, LoJack, OEM) |
| **Fully Aligned** | 27.03% (11,125 vehicles) |
| **Critical Exceptions** | 397 vehicles |
| **Refresh Schedule** | Daily at 6 AM CT |

## What This Dashboard Tracks

### Data Sources

| Source | System | Purpose | Coverage |
|--------|--------|---------|----------|
| **CDK** | DMS (Source of Truth) | Dealer inventory management | 21,321 vehicles |
| **vAuto** | Marketing Platform | Online listings & pricing | 19,468 vehicles |
| **LoJack** | GPS Tracking | Theft protection & lot management | 29,660 vehicles |
| **OEM** | Factory Allocations | Manufacturer vehicle allocations | 1,386 vehicles |

### Exception Types

| Priority | Exception | Count | Business Impact |
|----------|-----------|-------|-----------------|
| **CRITICAL** | OEM allocation not in CDK | 397 | $15.9M at risk |
| **HIGH** | In CDK but not marketed | 5,260 | $184.1M not advertised |
| **HIGH** | Ghost listings (vAuto but not CDK) | 3,283 | Customer frustration |
| **MEDIUM** | No LoJack tracking | 4,936 | $420M theft exposure |
| **OK** | Core systems aligned | 11,125 | No action needed |

## Financial Impact

| Risk Category | Value |
|---------------|-------|
| Inventory not being marketed | $184.1 Million |
| Monthly floorplan cost at risk | $2.76 Million |
| Vehicles without GPS tracking | $420 Million |
| OEM allocations at risk | $15.9 Million |

## Architecture

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│   CDK   │  │  vAuto  │  │ LoJack  │  │   OEM   │
│  (DMS)  │  │(Market) │  │  (GPS)  │  │(Factory)│
└────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘
     │            │            │            │
     └────────────┼────────────┼────────────┘
                  │
           ┌──────▼──────┐
           │  BigQuery   │
           │   Views     │
           └──────┬──────┘
                  │
           ┌──────▼──────┐
           │   Cloud     │
           │  Function   │
           └──────┬──────┘
                  │
           ┌──────▼──────┐
           │   Cloud     │◄─── Cloud Scheduler
           │  Storage    │     (Daily 6 AM CT)
           └──────┬──────┘
                  │
           ┌──────▼──────┐
           │    HTML     │
           │  Dashboard  │
           └─────────────┘
```

## Files

| File | Description |
|------|-------------|
| `index.html` | Interactive dashboard with charts and KPIs |
| `dashboard_data.json` | Auto-refreshed data from BigQuery |
| `export_vin_data.py` | Local data export script |
| `cloud_function/main.py` | Cloud Function for automated refresh |
| `cloud_function/requirements.txt` | Python dependencies |

## GCP Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Cloud Storage | `sonorous-key-320714-vin-dashboard` | Static hosting |
| Cloud Function | `refresh-vin-dashboard` | Data refresh |
| Cloud Scheduler | `vin-dashboard-daily-refresh` | Daily trigger |

## Manual Refresh

```bash
curl https://us-central1-sonorous-key-320714.cloudfunctions.net/refresh-vin-dashboard
```

## Local Development

```bash
# Export data locally
python export_vin_data.py

# Upload to Cloud Storage
gsutil cp index.html gs://sonorous-key-320714-vin-dashboard/
gsutil cp dashboard_data.json gs://sonorous-key-320714-vin-dashboard/
```

## BigQuery Views

The dashboard queries these views in the `inventory_exception` dataset:

- `VIN_Exception_Report` - Main consolidated report
- `Exception_Summary` - Counts by status
- `Critical_Exceptions` - Priority 1 items
- `Not_Marketed` - CDK but not vAuto
- `No_Tracking` - CDK but no LoJack
- `OEM_Not_Received` - Allocated but not in CDK
- `Combination_Matrix` - All flag combinations

## Documentation

- [Confluence Wiki](https://dodgemiami-team-e6pomihc.atlassian.net/wiki/pages/viewpage.action?pageId=137822210)

## Cost

| Component | Monthly |
|-----------|---------|
| Cloud Storage | < $0.01 |
| Cloud Function | < $0.01 |
| BigQuery queries | ~ $0.50 |
| Cloud Scheduler | Free |
| **Total** | < $1/month |

---

Built for Ahmed Group | Data Engineering Team
