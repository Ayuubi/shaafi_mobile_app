import frappe
import datetime
import time
from frappe.utils import now_datetime
from shaafi_mobile_app.utils.response_utils import response_util

@frappe.whitelist()
def get_all_banners():
    start_time = time.time()

    try:
        # Normalize to `date` to avoid comparing `datetime.datetime` with `datetime.date`.
        current_date = now_datetime().date()

        # Step 1: Fetch all banners
        banners = frappe.get_all(
            "Doctor banners",  
            fields=[
                "name",
                "banner_image",
                "banner_type",
                "title",
                "description",
                "details",
                "valid_from",
                "valid_till"
            ],
            order_by="valid_from desc"
        )

        # Step 2: Filter only expired 'Service' banners
        active_banners = []
        for banner in banners:
            if banner["banner_type"] == "Service":
                valid_till = banner.get("valid_till")
                # if not valid_till or valid_till > current_time:
                # Only include if valid_till is present and in the future
                if valid_till:
                    # `valid_till` may come back as `datetime.date` (or sometimes `datetime.datetime`).
                    if isinstance(valid_till, datetime.datetime):
                        valid_till_date = valid_till.date()
                    elif isinstance(valid_till, datetime.date):
                        valid_till_date = valid_till
                    else:
                        # Fallback for string-ish values coming from DB serialization.
                        valid_till_date = datetime.datetime.strptime(str(valid_till), "%Y-%m-%d").date()

                    if valid_till_date > current_date:
                        active_banners.append(banner)
            else:
                active_banners.append(banner)


        if not active_banners:
            return response_util(
                status="error",
                message="No banners found.",
                data=[],
                http_status_code=404
            )

        return response_util(
            status="success",
            message="Banners fetched successfully.",
            data=active_banners,
            http_status_code=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_all_banners failed")
        return response_util(
            status="error",
            message="An error occurred while fetching banners.",
            data=None,
            error=str(e),
            http_status_code=500
        )
