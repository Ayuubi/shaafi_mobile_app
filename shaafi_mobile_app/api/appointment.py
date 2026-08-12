import frappe
from datetime import datetime
from shaafi_mobile_app.utils.response_utils import response_util
from shaafi_mobile_app.utils.erpnext_utils import get_mobile_app_defaults
from shaafi_mobile_app.utils.phone_utils import normalize_somali_mobile, mobile_variants
from shaafi_mobile_app.utils.trace_utils import (
    appointment_trace_context,
    log_mobile_api_failure,
)


def calculate_appointment_details(PID, doctor_practitioner, appointment_date):
    """Calculates pricing, type, and follow-up status in one place (DRY)."""
    appointment_date_obj = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    customer_group = frappe.db.get_value("Patient", PID, "customer_group")
    doct_amount = (
        frappe.db.get_value("Healthcare Practitioner", doctor_practitioner, "op_consulting_charge")
        or 0
    )

    original_amount = float(doct_amount)
    payable_amount = original_amount
    appointment_type = "New Patient"
    is_follow_up = False

    # Check follow-up (100% discount)
    fee_validity = frappe.get_all(
        "Fee Validity",
        filters={"patient": PID, "practitioner": doctor_practitioner, "status": "Pending"},
        fields=["valid_till", "visited", "max_visits"],
        order_by="creation desc",
        limit_page_length=1,
    )

    if fee_validity:
        fv = fee_validity[0]
        valid_till = datetime.strptime(str(fv["valid_till"]), "%Y-%m-%d").date()
        if appointment_date_obj <= valid_till and fv["visited"] < fv["max_visits"]:
            return 0, "Follow Up", True, original_amount

    # Apply Membership discount (50%)
    if customer_group == "Membership":
        payable_amount = original_amount * 0.5

    return payable_amount, appointment_type, is_follow_up, original_amount


@frappe.whitelist()
def validate_appointment_booking(PID, doctor_practitioner, appointment_date):
    try:
        if not all([PID, doctor_practitioner, appointment_date]):
            return response_util(
                status="error",
                message="PID, Doctor Practitioner, and Appointment Date are required.",
                http_status_code=400,
            )

        if not frappe.db.exists("Patient", PID):
            return response_util(
                status="error",
                message=f"Patient with ID {PID} does not exist.",
                http_status_code=404,
            )

        if not frappe.db.exists("Healthcare Practitioner", doctor_practitioner):
            return response_util(
                status="error",
                message=f"Doctor {doctor_practitioner} does not exist.",
                http_status_code=404,
            )

        if frappe.db.exists(
            "Que",
            {"patient": PID, "practitioner": doctor_practitioner, "date": appointment_date, "docstatus": ("<", 2)},
        ):
            return response_util(
                status="error",
                message="An appointment for this patient with the same doctor on this date already exists.",
                http_status_code=400,
            )

        payable_amount, appointment_type, is_follow_up, original_amount = calculate_appointment_details(
            PID, doctor_practitioner, appointment_date
        )
        defaults = get_mobile_app_defaults()

        temp_doc = frappe.new_doc("Que")
        temp_doc.update({
            "patient": PID,
            "practitioner": doctor_practitioner,
            "date": appointment_date,
            "paid_amount": payable_amount,
            "mode_of_payment": defaults["mode_of_payment"],
            "cost_center": defaults["cost_center"],
            "appointment_source": "Mobile App",
            "que_type": appointment_type,
            "follow_up": is_follow_up,
        })
        temp_doc.run_method("validate")

        customer_group = frappe.db.get_value("Patient", PID, "customer_group")

        return response_util(
            status="success",
            message="Patient is eligible to book appointment.",
            data={
                "appointment_type": appointment_type,
                "paid_amount": payable_amount,
                "original_amount": original_amount,
                "is_follow_up": is_follow_up,
                "customer_group": customer_group,
            },
            http_status_code=200,
        )

    except frappe.ValidationError as ve:
        log_mobile_api_failure(
            "validate_appointment_booking",
            "validation_error",
            appointment_trace_context(PID, doctor_practitioner, appointment_date),
            error=ve,
            http_status_code=400,
        )
        return response_util(
            status="error",
            message="Validation failed during appointment simulation.",
            error=str(ve),
            http_status_code=400,
        )
    except Exception as e:
        log_mobile_api_failure(
            "validate_appointment_booking",
            "unexpected_error",
            appointment_trace_context(PID, doctor_practitioner, appointment_date),
            error=e,
            http_status_code=500,
        )
        return response_util(
            status="error",
            message="Unexpected error while validating appointment booking.",
            error=str(e),
            http_status_code=500,
        )


@frappe.whitelist()
def create_appointment(PID, doctor_practitioner, appointment_date):
    try:
        if not all([PID, doctor_practitioner, appointment_date]):
            return response_util(
                status="error",
                message="PID, Doctor Practitioner, and Appointment Date are required.",
                data=None,
                http_status_code=400,
            )

        defaults = get_mobile_app_defaults()
        if not defaults.get("cost_center") or not defaults.get("mode_of_payment"):
            return response_util(
                status="error",
                message="Mobile App Settings not configured. Please set Cost Center and Mode of Payment.",
                http_status_code=500,
            )

        if not frappe.db.exists("Patient", PID):
            return response_util(
                status="error",
                message=f"Patient with ID {PID} does not exist.",
                data=None,
                http_status_code=404,
            )

        if not frappe.db.exists("Healthcare Practitioner", doctor_practitioner):
            return response_util(
                status="error",
                message=f"Doctor with ID {doctor_practitioner} does not exist.",
                data=None,
                http_status_code=404,
            )

        if frappe.db.exists(
            "Que",
            {"patient": PID, "practitioner": doctor_practitioner, "date": appointment_date, "docstatus": ("<", 2)},
        ):
            return response_util(
                status="error",
                message="An appointment for this patient with the same doctor on this date already exists.",
                http_status_code=400,
            )

        payable_amount, appointment_type, is_follow_up, original_amount = calculate_appointment_details(
            PID, doctor_practitioner, appointment_date
        )

        appointment = frappe.new_doc("Que")
        appointment.update({
            "patient": PID,
            "practitioner": doctor_practitioner,
            "date": appointment_date,
            "paid_amount": payable_amount,
            "mode_of_payment": defaults["mode_of_payment"],
            "cost_center": defaults["cost_center"],
            "appointment_source": "Mobile App",
            "que_type": appointment_type,
            "follow_up": is_follow_up,
        })

        appointment.insert()
        frappe.db.commit()

        return response_util(
            status="success",
            message="Appointment created successfully",
            data={
                "appointment_id": appointment.name,
                "appointment_type": appointment_type,
                "amount_charged": payable_amount,
                "original_amount": original_amount,
                "token_no": appointment.token_no,
            },
            http_status_code=200,
        )

    except Exception as e:
        log_mobile_api_failure(
            "create_appointment",
            "unexpected_error",
            appointment_trace_context(PID, doctor_practitioner, appointment_date),
            error=e,
            http_status_code=500,
        )
        return response_util(
            status="error",
            message="An error occurred while creating the appointment.",
            error=str(e),
            data=None,
            http_status_code=500,
        )      
        
        
@frappe.whitelist()
def get_appointments(mobile_no=None):
    canonical_mobile = None

    if not mobile_no:
        frappe.response['http_status_code'] = 400
        return {
            "status": "error",
            "msg": "Mobile No is required."
        }

    canonical_mobile = normalize_somali_mobile(mobile_no)
    if not canonical_mobile:
        frappe.response['http_status_code'] = 400
        return {
            "status": "error",
            "msg": "Invalid mobile number."
        }

    try:
        mobile_numbers = mobile_variants(canonical_mobile)
        cutoff_date = frappe.utils.add_days(frappe.utils.today(), -90)

        appointments = frappe.get_all(
            "Que",
            filters={"mobile": ["in", mobile_numbers], "docstatus": ["<", 2], "creation": [">=", cutoff_date]},
            fields=["name", "patient", "patient_name", "practitioner", "paid_amount", "creation",
                    "appointment_source", "token_no"],
            order_by="creation desc"
        )

        if not appointments:
            frappe.response['http_status_code'] = 404
            return {
                "status": "error",
                "msg": f"No appointments found for patient: {canonical_mobile}",
                "Data": None
            }

        frappe.response['http_status_code'] = 200
        return {
            "status": "success",
            "msg": "Appointments retrieved successfully",
            "Data": appointments
        }

    except Exception as e:
        log_mobile_api_failure(
            "get_appointments",
            "unexpected_error",
            appointment_trace_context(mobile=canonical_mobile),
            error=e,
            http_status_code=500,
        )
        frappe.response['http_status_code'] = 500
        return {
            "status": "error",
            "msg": "An error occurred while retrieving appointments.",
            "details": str(e)
        }
