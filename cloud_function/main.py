"""
VIN Exception Dashboard - Cloud Function for Automated Refresh
Triggered daily by Cloud Scheduler to update dashboard data
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

        # 1. Exception Summary
        summary_query = """
        SELECT
            EXCEPTION_STATUS,
            PRIORITY,
            COUNT(*) as vehicle_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        GROUP BY EXCEPTION_STATUS, PRIORITY
        ORDER BY PRIORITY, vehicle_count DESC
        """
        data['exception_summary'] = [dict(row) for row in client.query(summary_query)]

        # 2. Source Totals
        totals_query = """
        SELECT
            COUNT(*) as total_vins,
            SUM(CDK_FLAG) as cdk_count,
            SUM(VAUTO_FLAG) as vauto_count,
            SUM(LOJACK_FLAG) as lojack_count,
            SUM(OEM_FLAG) as oem_count
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        """
        totals = list(client.query(totals_query))[0]
        data['summary'] = {
            'total_vins': totals.total_vins,
            'cdk_count': totals.cdk_count,
            'vauto_count': totals.vauto_count,
            'lojack_count': totals.lojack_count,
            'oem_count': totals.oem_count
        }

        # 3. Combination Matrix
        matrix_query = """
        SELECT
            CDK_FLAG, VAUTO_FLAG, LOJACK_FLAG, OEM_FLAG,
            COUNT(*) as vehicle_count
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        GROUP BY CDK_FLAG, VAUTO_FLAG, LOJACK_FLAG, OEM_FLAG
        ORDER BY vehicle_count DESC
        LIMIT 15
        """
        data['combination_matrix'] = [dict(row) for row in client.query(matrix_query)]

        # 4. Make Distribution
        make_query = """
        SELECT
            IFNULL(makename, 'Unknown') as make,
            COUNT(*) as total_vehicles,
            SUM(CASE WHEN PRIORITY IN (1,2) THEN 1 ELSE 0 END) as high_priority_exceptions
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE CDK_FLAG = 1
        GROUP BY makename
        ORDER BY total_vehicles DESC
        LIMIT 10
        """
        data['make_distribution'] = [dict(row) for row in client.query(make_query)]

        # 5. Financial Metrics
        financial_query = """
        SELECT
            ROUND(AVG(vauto_price), 0) as avg_price,
            ROUND(SUM(CASE WHEN CDK_FLAG = 1 AND VAUTO_FLAG = 1 THEN vauto_price ELSE 0 END), 0) as marketed_value,
            ROUND(AVG(vauto_age), 1) as avg_age_days
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE vauto_price > 0
        """
        financial = list(client.query(financial_query))[0]
        data['financial'] = {
            'avg_price': float(financial.avg_price) if financial.avg_price else 0,
            'marketed_value': float(financial.marketed_value) if financial.marketed_value else 0,
            'avg_age_days': float(financial.avg_age_days) if financial.avg_age_days else 0
        }

        # 6. Aging Distribution
        aging_query = """
        SELECT
            CASE
                WHEN vauto_age <= 30 THEN '0-30 days'
                WHEN vauto_age <= 60 THEN '31-60 days'
                WHEN vauto_age <= 90 THEN '61-90 days'
                ELSE '90+ days'
            END as age_bucket,
            COUNT(*) as vehicle_count,
            ROUND(AVG(vauto_price), 0) as avg_price
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE vauto_age IS NOT NULL AND vauto_price > 0
        GROUP BY age_bucket
        ORDER BY MIN(vauto_age)
        """
        data['aging'] = [dict(row) for row in client.query(aging_query)]

        # 7. Impact Metrics
        not_marketed_query = """
        SELECT
            COUNT(*) as not_marketed_count,
            ROUND(COUNT(*) * 35000, 0) as estimated_value
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE CDK_FLAG = 1 AND VAUTO_FLAG = 0
        """
        not_marketed = list(client.query(not_marketed_query))[0]

        no_tracking_query = """
        SELECT
            COUNT(*) as no_tracking_count,
            COUNT(*) * 45000 as value_at_risk
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE CDK_FLAG = 1 AND LOJACK_FLAG = 0
        """
        no_tracking = list(client.query(no_tracking_query))[0]

        oem_query = """
        SELECT
            COUNT(*) as oem_not_received,
            COUNT(*) * 40000 as allocation_value
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE CDK_FLAG = 0 AND OEM_FLAG = 1
        """
        oem = list(client.query(oem_query))[0]

        data['impact'] = {
            'not_marketed_count': not_marketed.not_marketed_count,
            'not_marketed_value': float(not_marketed.estimated_value) if not_marketed.estimated_value else 0,
            'no_tracking_count': no_tracking.no_tracking_count,
            'no_tracking_value': no_tracking.value_at_risk,
            'oem_not_received': oem.oem_not_received,
            'oem_value_at_risk': oem.allocation_value
        }

        # 8. Critical VINs
        critical_query = """
        SELECT
            vin,
            IFNULL(makename, 'Unknown') as make,
            IFNULL(modelname, 'Unknown') as model,
            year,
            EXCEPTION_STATUS
        FROM `sonorous-key-320714.inventory_exception.VIN_Exception_Report`
        WHERE PRIORITY = 1
        LIMIT 20
        """
        data['critical_vins'] = [dict(row) for row in client.query(critical_query)]

        # Add metadata
        data['lastUpdated'] = datetime.now().isoformat()
        data['generated_by'] = 'refresh_vin_dashboard'

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
        return f"VIN Exception Dashboard refreshed at {data['lastUpdated']} with {total_vins:,} vehicles tracked"

    except Exception as e:
        return f"Error refreshing dashboard: {str(e)}", 500
