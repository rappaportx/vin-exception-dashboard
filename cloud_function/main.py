"""
VIN Exception Dashboard - Cloud Function for Automated Refresh
Triggered daily by Cloud Scheduler to update dashboard data
Now includes 5 data sources: CDK, vAuto, LoJack, OEM, FloorPlan
"""

import json
import functions_framework
from datetime import datetime
from google.cloud import bigquery
from google.cloud import storage

PROJECT_ID = 'sonorous-key-320714'
BUCKET_NAME = 'sonorous-key-320714-vin-dashboard'
OUTPUT_FILE = 'dashboard_data.json'

@functions_framework.http
def refresh_vin_dashboard(request):
    """HTTP Cloud Function to refresh VIN exception dashboard data."""
    try:
        client = bigquery.Client(project=PROJECT_ID)
        data = {}

        # 1. Exception Summary (5 Sources)
        summary_query = """
        SELECT
            EXCEPTION_STATUS,
            PRIORITY,
            COUNT(*) as vehicle_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        GROUP BY EXCEPTION_STATUS, PRIORITY
        ORDER BY PRIORITY, vehicle_count DESC
        """
        data['exception_summary'] = [dict(row) for row in client.query(summary_query)]

        # 2. Source Totals (5 Sources)
        totals_query = """
        SELECT
            COUNT(*) as total_vins,
            SUM(CDK_FLAG) as cdk_count,
            SUM(VAUTO_FLAG) as vauto_count,
            SUM(LOJACK_FLAG) as lojack_count,
            SUM(OEM_FLAG) as oem_count,
            SUM(FLOORPLAN_FLAG) as floorplan_count
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        """
        totals = list(client.query(totals_query))[0]
        data['summary'] = {
            'total_vins': totals.total_vins,
            'cdk_count': totals.cdk_count,
            'vauto_count': totals.vauto_count,
            'lojack_count': totals.lojack_count,
            'oem_count': totals.oem_count,
            'floorplan_count': totals.floorplan_count
        }

        # 3. Combination Matrix (5 Sources)
        matrix_query = """
        SELECT
            CDK_FLAG, VAUTO_FLAG, LOJACK_FLAG, OEM_FLAG, FLOORPLAN_FLAG,
            COUNT(*) as vehicle_count
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        GROUP BY CDK_FLAG, VAUTO_FLAG, LOJACK_FLAG, OEM_FLAG, FLOORPLAN_FLAG
        ORDER BY vehicle_count DESC
        LIMIT 20
        """
        data['combination_matrix'] = [dict(row) for row in client.query(matrix_query)]

        # 4. FloorPlan Without CDK (Critical)
        floorplan_risk_query = """
        SELECT
            COUNT(*) as floorplan_without_cdk,
            COUNT(*) * 35000 as estimated_value
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        WHERE CDK_FLAG = 0 AND FLOORPLAN_FLAG = 1
        """
        floorplan_risk = list(client.query(floorplan_risk_query))[0]
        data['floorplan_risk'] = {
            'count': floorplan_risk.floorplan_without_cdk,
            'value': float(floorplan_risk.estimated_value) if floorplan_risk.estimated_value else 0
        }

        # 5. Not Marketed
        not_marketed_query = """
        SELECT
            COUNT(*) as not_marketed_count,
            ROUND(COUNT(*) * 35000, 0) as estimated_value
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        WHERE CDK_FLAG = 1 AND VAUTO_FLAG = 0
        """
        not_marketed = list(client.query(not_marketed_query))[0]
        data['not_marketed'] = {
            'count': not_marketed.not_marketed_count,
            'value': float(not_marketed.estimated_value) if not_marketed.estimated_value else 0
        }

        # 6. No Tracking
        no_tracking_query = """
        SELECT
            COUNT(*) as no_tracking_count,
            COUNT(*) * 45000 as value_at_risk
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        WHERE CDK_FLAG = 1 AND LOJACK_FLAG = 0
        """
        no_tracking = list(client.query(no_tracking_query))[0]
        data['no_tracking'] = {
            'count': no_tracking.no_tracking_count,
            'value': no_tracking.value_at_risk
        }

        # 7. OEM Not Received
        oem_query = """
        SELECT
            COUNT(*) as oem_not_received,
            COUNT(*) * 40000 as allocation_value
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        WHERE CDK_FLAG = 0 AND OEM_FLAG = 1
        """
        oem = list(client.query(oem_query))[0]
        data['oem_risk'] = {
            'count': oem.oem_not_received,
            'value': oem.allocation_value
        }

        # 8. Critical VINs (FloorPlan without CDK - sample)
        critical_query = """
        SELECT
            vin,
            FLOORPLAN_FLAG,
            OEM_FLAG,
            EXCEPTION_STATUS
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_5_Source`
        WHERE PRIORITY = 1
        LIMIT 25
        """
        data['critical_vins'] = [dict(row) for row in client.query(critical_query)]

        # Add metadata
        data['lastUpdated'] = datetime.now().isoformat()
        data['generated_by'] = 'refresh_vin_dashboard'
        data['sources'] = ['CDK', 'vAuto', 'LoJack', 'OEM', 'FloorPlan']

        # Upload to Cloud Storage
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(OUTPUT_FILE)
        blob.upload_from_string(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        blob.cache_control = 'no-cache, max-age=300'
        blob.patch()

        total_vins = data['summary']['total_vins']
        floorplan_risk_count = data['floorplan_risk']['count']
        return f"VIN Exception Dashboard refreshed at {data['lastUpdated']} - {total_vins:,} vehicles, {floorplan_risk_count:,} FloorPlan at risk"

    except Exception as e:
        return f"Error refreshing dashboard: {str(e)}", 500
