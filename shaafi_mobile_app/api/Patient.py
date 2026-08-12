import frappe
from shaafi_mobile_app.utils.response_utils import response_util
from shaafi_mobile_app.utils.phone_utils import normalize_somali_mobile, mobile_variants
from shaafi_mobile_app.utils.trace_utils import log_mobile_api_failure, patient_trace_context


@frappe.whitelist()
def can_register_patient(full_name, mobile_number):
    if not all([full_name, mobile_number]):
        return response_util(
            status="error",
            message="Full name and mobile number are required.",
            http_status_code=400
        )

    canonical = normalize_somali_mobile(mobile_number)
    if not canonical:
        return response_util(
            status="error",
            message="Invalid mobile number.",
            http_status_code=400
        )

    exists = frappe.db.exists("Patient", {"mobile_no": ["in", mobile_variants(canonical)], "first_name": full_name})
    if exists:
        return response_util(
            status="error",
            message="This patient already exists.",
            http_status_code=409
        )

    return response_util(
        status="success",
        message="Patient not exist You can register",
        data={"otp_sent": True},
        http_status_code=200
    )
        

@frappe.whitelist()
def patient_login(mobile_number):
    if not mobile_number:
        return response_util(
            status="error",
            message="Mobile number is required!",
            http_status_code=400
        )

    canonical = normalize_somali_mobile(mobile_number)
    if not canonical:
        return response_util(
            status="error",
            message="Invalid mobile number.",
            http_status_code=400
        )

    try:
        patient = frappe.get_value(
            "Patient",
            {"mobile_no": ["in", mobile_variants(canonical)]},
            "name",
            order_by="creation asc"
        )

        if patient:
            patient_info = frappe.get_doc("Patient", patient)
            
            
            return response_util(
                status="success",
                message="Login successful",
                data={
                    "patient_id": patient_info.name,
                    "first_name": patient_info.first_name,
                    "mobile": patient_info.mobile_no,
                    "district": patient_info.territory,
                    "age": patient_info.p_age,
                    "Gender": patient_info.sex,
                    "image": patient_info.get('image')
                },
                http_status_code=200
            )
        else:
            return response_util(
                status="error",
                message="Patient not found with the provided mobile number.",
                http_status_code=404
            )

    except Exception as e:
        log_mobile_api_failure(
            "patient_login",
            "unexpected_error",
            patient_trace_context(mobile=canonical),
            error=e,
            http_status_code=500,
        )
        return response_util(
            status="error",
            message="An error occurred while logging in",
            error=str(e),
            http_status_code=500
        )
        

@frappe.whitelist()
def register_patient(pat_full_name, pat_gender, pat_age, pat_age_type, pat_mobile_number, pat_district):
    try:
        if not pat_full_name:
            return response_util(
                status="error",
                message="Full Name is required.",
                http_status_code=400
            )

        create_doc = frappe.new_doc("Patient")
        
        create_doc.first_name = pat_full_name
        create_doc.sex = pat_gender
        create_doc.p_age = pat_age
        create_doc.age_type = pat_age_type
        canonical_mobile = normalize_somali_mobile(pat_mobile_number)
        if not canonical_mobile:
            return response_util(
                status="error",
                message="Invalid mobile number.",
                http_status_code=400
            )
        create_doc.mobile_no = canonical_mobile
        create_doc.territory = pat_district
        create_doc.insert()
        frappe.db.commit()

        if create_doc:
            return response_util(
                status="success",
                message="Patient registered successfully.",
                http_status_code=200
            )
        else:
            return response_util(
                status="error",
                message="Patient registration failed.",
                http_status_code=404
            )

    except Exception as e:
        log_mobile_api_failure(
            "register_patient",
            "unexpected_error",
            patient_trace_context(
                mobile=normalize_somali_mobile(pat_mobile_number),
                full_name=pat_full_name,
            ),
            error=e,
            http_status_code=500,
        )
        return response_util(
            status="error",
            message="An error occurred while registering the patient.",
            error=str(e),
            http_status_code=500
        )
          

@frappe.whitelist()
def get_patients_with_same_mobile(mobile_number, doctor_name=None):
    if not mobile_number:
        return response_util(
            status="error",
            message="Mobile number is required.",
            http_status_code=400
        )

    canonical = normalize_somali_mobile(mobile_number)
    if not canonical:
        return response_util(
            status="error",
            message="Invalid mobile number.",
            http_status_code=400
        )

    try:
        patients = frappe.get_all(
            "Patient",
            filters={"mobile_no": ["in", mobile_variants(canonical)]},
            fields=[
                "name", "first_name", "p_age", "image",
                "customer_group", "creation"
            ],
            order_by="creation asc"
        )

        if not patients:
            return response_util(
                status="error",
                message=f"No patients found for mobile number: {mobile_number}",
                http_status_code=404
            )

        enriched_patients = []
        for patient in patients:
            patient_id = patient.get("name")

            # Format image URL
            patient["image"] = patient.get("image")

            # Ensure required fields exist
            patient["customer_group"] = patient.get("customer_group") or "All Customer Groups"

            # Try to get the latest Fee Validity record
            fee_validity = frappe.get_all(
                "Fee Validity",
                filters={"patient": patient_id, "practitioner" : doctor_name},
                fields=["name", "start_date", "valid_till", "status"],
                order_by="creation desc",
                limit_page_length=1
            )

            if fee_validity:
                fee = fee_validity[0]
                patient["followupId"] = fee.get("name")
                patient["followupStartDate"] = fee.get("start_date")
                patient["followupExpirationDate"] = fee.get("valid_till")
                patient["followupStatus"] = fee.get("status")
            else:
                patient["followupId"] = None
                patient["followupStartDate"] = None
                patient["followupExpirationDate"] = None
                patient["followupStatus"] = None

            # Rename fields for frontend consistency
            enriched_patients.append({
                "name": patient["name"],
                "first_name": patient["first_name"],
                "p_age": patient["p_age"],
                "image": patient["image"],
                "customer_group": patient["customer_group"],
                "followupId": patient["followupId"],
                "followupStartDate": patient["followupStartDate"],
                "followupExpirationDate": patient["followupExpirationDate"],
                "followupStatus": patient["followupStatus"]
            })

        return response_util(
            status="success",
            message="Patients found successfully.",
            data=enriched_patients,
            http_status_code=200
        )

    except Exception as e:
        log_mobile_api_failure(
            "get_patients_with_same_mobile",
            "unexpected_error",
            patient_trace_context(mobile=canonical),
            error=e,
            http_status_code=500,
        )
        return response_util(
            status="error",
            message="An error occurred while retrieving patients.",
            error=str(e),
            http_status_code=500
        )
        
        
@frappe.whitelist(allow_guest=True)
def get_patient_profile(patient_id, fcm_token=None):
    try:
        patient_doc = frappe.get_doc("Patient", patient_id)

        # Safely update FCM token if the field exists and token is provided
        if fcm_token and hasattr(patient_doc, "fcm_token"):
            if not patient_doc.fcm_token or patient_doc.fcm_token != fcm_token:
                patient_doc.fcm_token = fcm_token
                patient_doc.save(ignore_permissions=True)
                frappe.db.commit()

        return response_util(
            status="success",
            message="Patient profile retrieved successfully",
            data={
                "patient_id": patient_doc.name,
                "first_name": patient_doc.first_name,
                "gender": patient_doc.sex,
                "age": patient_doc.p_age,
                "mobile": patient_doc.mobile_no,
                "district": patient_doc.territory,
                "image": patient_doc.get('image')
            },
            http_status_code=200
        )

    except frappe.DoesNotExistError:
        return response_util(
            status="error",
            message=f"Patient with ID '{patient_id}' does not exist.",
            http_status_code=404
        )
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Patient Profile Error")
        return response_util(
            status="error",
            message="An unexpected error occurred.",
            error=e,
            http_status_code=500
        )


@frappe.whitelist()
def get_districts():
    try:
        districts = frappe.db.get_all("Territory", fields=["territory_name"])
        return response_util(
            status="success",
            message="Districts found successfully.",
            data=districts,
            http_status_code=200
        )
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Districts Error")
        return response_util(
            status="error",
            message="An error occurred while fetching districts.",
            error=e,
            http_status_code=500
        )

@frappe.whitelist()
def get_all_departments():
    try:
        departments = frappe.db.get_all("Department", fields=["name", "department_name"])

        if not departments:
            return response_util(
                status="error",
                message="No departments found in the system.",
                http_status_code=404
            )

        return response_util(
            status="success",
            message="Departments retrieved successfully.",
            data=departments,
            http_status_code=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Departments Error")
        return response_util(
            status="error",
            message="An error occurred while retrieving departments.",
            error=e,
            http_status_code=500
        )
        
        
        
@frappe.whitelist()
def submit_patient_feedback(
    patient_id,
    feedback_type,
    rating,
    comments=None,
    app_feedback_category=None,
    app_version=None,
    device_info=None
):
    """
    Submit patient feedback with proper validation and auto-naming
    Args:
        patient_id (str): Required - Patient document ID
        feedback_type (str): Required - From predefined options
        rating (float): Required - 1-5 scale
        comments (str): Optional - Feedback details
        app_feedback_category (str): Required if feedback_type is app related
        app_version (str): Optional - App version
        device_info (str): Optional - JSON string of device info
    Returns:
        dict: {'status': 'success/error', 'message': str, 'data': dict}
    """
    try:
        # === VALIDATION ===
        if not all([patient_id, feedback_type, rating]):
            return response_util(
                status="error",
                message="Patient ID, feedback type and rating are required",
                http_status_code=400
            )

        # Validate patient exists
        if not frappe.db.exists("Patient", patient_id):
            return response_util(
                status="error",
                message="Patient not found",
                http_status_code=404
            )

        # Validate feedback type
        valid_types = [
            "General Feedback", "Doctor Feedback", "Facility Feedback",
            "Appointment Feedback", "Service Feedback", "App Related Feedback"
        ]
        if feedback_type not in valid_types:
            return response_util(
                status="error",
                message=f"Invalid feedback type. Must be one of: {', '.join(valid_types)}",
                http_status_code=400
            )

        # Validate rating
        try:
            rating = float(rating)
            if not (1 <= rating <= 5):
                raise ValueError
        except ValueError:
            return response_util(
                status="error",
                message="Rating must be a number between 1 and 5",
                http_status_code=400
            )

        # Validate app-specific fields
        if feedback_type == "App Related Feedback" and not app_feedback_category:
            return response_util(
                status="error",
                message="App feedback category is required for app-related feedback",
                http_status_code=400
            )

        # === CREATE FEEDBACK ===
        feedback = frappe.new_doc("Patient Feedback")
        feedback.update({
            "patient": patient_id,
            "feedback_type": feedback_type,
            "rating": rating,
            "comments": comments,
            "status": "Open"  # Default status
        })

        # Add app-specific fields if applicable
        if feedback_type == "App Related Feedback":
            feedback.update({
                "app_feedback_category": app_feedback_category,
                "app_version": app_version or "1.0.0",
                "device_info": device_info or "{}"
            })

        # Auto-set patient name
        feedback.patient_name = frappe.db.get_value("Patient", patient_id, "patient_name")

        # Save with auto-naming (PFB-YYYYMM-####)
        feedback.insert(ignore_permissions=True)
        frappe.db.commit()

        # === RESPONSE ===
        return response_util(
            status="success",
            message="Feedback submitted successfully",
            data={
                "feedback_id": feedback.name,
                "patient_name": feedback.patient_name,
                "submitted_on": feedback.creation
            },
            http_status_code=201
        )

    except Exception as e:
        frappe.log_error(
            title="Patient Feedback Submission Failed",
            message=frappe.get_traceback()
        )
        return response_util(
            status="error",
            message="Failed to submit feedback",
            error=str(e),
            http_status_code=500
        )