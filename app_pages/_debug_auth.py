import streamlit as st
from ta_core.services.auth_service import get_supabase

st.title("Auth debug")
url_ok = "SUPABASE_URL" in st.secrets and bool(st.secrets["SUPABASE_URL"])
key_ok = "SUPABASE_ANON_KEY" in st.secrets and bool(st.secrets["SUPABASE_ANON_KEY"])
st.write("Secrets present:", url_ok and key_ok)

email = st.text_input("Email").strip()
pwd   = st.text_input("Password", type="password")

if st.button("Try sign-in"):
    sb = get_supabase()
    try:
        sb.auth.sign_in_with_password({"email": email, "password": pwd})
        st.success("OK")
    except Exception as e:
        st.error(repr(e))
