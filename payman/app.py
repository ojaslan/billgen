from dotenv import load_dotenv
import os

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
payman_api_secret = os.getenv("PAYMAN_API_SECRET")

import streamlit as st
import os
import tempfile
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
import openai
import json

# Configure the app
st.set_page_config(
    page_title="Bill Buddy - AI Bill Payment Agent",
    page_icon="💰",
    layout="wide"
)

# Initialize API keys
openai_api_key = os.environ.get("OPENAI_API_KEY")
payman_api_secret = os.environ.get("PAYMAN_API_SECRET")


def extract_text_from_pdf(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
        temp_pdf.write(uploaded_file.getvalue())
        temp_pdf_path = temp_pdf.name
    
    try:
        doc = fitz.open(temp_pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    finally:
        os.unlink(temp_pdf_path)

def extract_text_from_image(uploaded_file):
    image = Image.open(uploaded_file)
    return pytesseract.image_to_string(image)



def extract_payment_info(text):
    client = openai.OpenAI(api_key=openai_api_key)
    
    system_prompt = """
    Extract payment information from the bill text. Return a JSON object with:
    - name (payee name)
    - account_holder_name
    - account_number
    - routing_number
    - account_type (checking/savings)
    - account_holder_type (individual/business)
    - amount
    - due_date (YYYY-MM-DD)
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Failed to extract payment information: {e}")
        return None




def send_payment(payment_info):
    try:
        payman = Paymanai(
            x_payman_api_secret=payman_api_secret,
        )
        
        # Check for existing payee
        existing_payees = payman.payments.search_payees(name=payment_info["name"])
        payee_id = existing_payees[0]["id"] if existing_payees else None
        
        # Create new payee if needed
        if not payee_id:
            payee = payman.payments.create_payee(
                type="US_ACH",
                name=payment_info["name"],
                account_holder_name=payment_info["account_holder_name"],
                account_number=payment_info["account_number"],
                routing_number=payment_info["routing_number"],
                account_type=payment_info["account_type"],
                account_holder_type=payment_info["account_holder_type"]
            )
            payee_id = payee.id
        
        # Send payment
        payment = payman.payments.send_payment(
            amount_decimal=float(payment_info["amount"]),
            payee_id=payee_id,
            memo=f"Payment for bill due on {payment_info.get('due_date', 'N/A')}"
        )
        
        return {"reference": payment.reference} if hasattr(payment, "reference") else {"status": "request_sent"}
            
    except Exception as e:
        st.error(f"Error processing payment: {e}")
        return None






def main():
    st.title("Bill Buddy - AI Bill Payment Agent 💰")
    
    uploaded_file = st.file_uploader("Upload a bill (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"])
    
    if uploaded_file:
        with st.spinner("Processing your bill..."):
            # Extract text
            text = extract_text_from_pdf(uploaded_file) if uploaded_file.type == "application/pdf" else extract_text_from_image(uploaded_file)
            
            # Extract payment information
            payment_info = extract_payment_info(text)
            
            if payment_info:
                # Display extracted information
                st.subheader("Extracted Payment Information")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Payee Name:**", payment_info.get("name", ""))
                    st.write("**Account Holder:**", payment_info.get("account_holder_name", ""))
                    st.write("**Account Number:**", payment_info.get("account_number", ""))
                    st.write("**Routing Number:**", payment_info.get("routing_number", ""))
                
                with col2:
                    st.write("**Account Type:**", payment_info.get("account_type", "checking"))
                    st.write("**Holder Type:**", payment_info.get("account_holder_type", "individual"))
                    st.write("**Amount:**", f"${payment_info.get('amount', 0.0):.2f}")
                    st.write("**Due Date:**", payment_info.get("due_date", ""))
                
                # Edit and submit payment
                if st.button("Pay Bill"):
                    with st.spinner("Processing payment..."):
                        result = send_payment(payment_info)
                        if result:
                            st.success("✅ Payment request created!")
                            if "reference" in result:
                                st.info(f"Reference ID: {result['reference']}")
                            st.warning("Please approve this payment in your [Payman Dashboard](https://app.paymanai.com)")
            else:
                st.error("Failed to extract payment information. Please try again with a clearer image or PDF.")

if __name__ == "__main__":
    main()
