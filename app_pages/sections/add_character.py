from __future__ import annotations
from datetime import timezone
from typing import Callable
import streamlit as st

from ta_core.services.auth_service import current_user_id
from ta_core.services.characters_service import (
    generate_or_get_code, verify_character_code, CODE_TTL_MINUTES,
)


def render(on_back: Callable[[], None]) -> None:
    st.header("Add Character")

    # Disclaimer with instructions
    with st.container(border=True):
        st.markdown(
            f"""
**How to link your Tibia character (step by step)**

1. **Enter your character name** exactly as it appears on Tibia.com.  
2. Click **Generate/Show code** to get a temporary code (valid for **{CODE_TTL_MINUTES} minutes**).  
3. Go to **Tibia.com → Your character → Edit → Comment/Description** and **paste the code** there.  
   *Tip:* Put the code on a separate line and save the changes.  
4. Wait a short moment (the TibiaData API may take **1–2 minutes** to refresh).  
5. Come back here and click **Verify code**.

**Notes**
- If the code expires, just generate a new one and update your comment again.  
- Make sure you are editing the **same character** you typed here.  
- Once verified, the character will be linked to your account.
            """,
            unsafe_allow_html=False,
        )

    uid = current_user_id()
    if not uid:
        st.info("Please sign in to continue.")
        st.button("← Back to Profile", on_click=on_back, type="secondary")
        return

    name = st.text_input("Character name", value=st.session_state.get("add_char_name", ""))
    st.session_state["add_char_name"] = name

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Generate/Show code", use_container_width=True, key="btn_gen_code"):
            if not name.strip():
                st.error("Please enter a character name.")
            else:
                try:
                    code, exp = generate_or_get_code(uid, name)
                    st.session_state["add_char_code"] = code
                    st.session_state["add_char_exp"] = exp
                except ValueError as e:
                    st.error(str(e))

        # Show code if exists
        code = st.session_state.get("add_char_code")
        exp = st.session_state.get("add_char_exp")
        if code and exp:
            st.success(f"Verification code (valid {CODE_TTL_MINUTES} min):")
            st.code(code, language="text")
            st.caption(f"Expires at (UTC): {exp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")

    with col2:
        st.caption("1) Put the code in your Tibia.com character **comment/description**.\n\n"
                   "2) Then press **Verify**.")
        if st.button("Verify code", use_container_width=True, key="btn_verify_code"):
            if not name.strip():
                st.error("Please enter a character name.")
            elif not st.session_state.get("add_char_code"):
                st.error("Generate a code first.")
            else:
                ok = verify_character_code(uid, name)
                last_comment = st.session_state.get("_last_verify_comment", "")
                if ok:
                    st.success("Character verified and linked to your account.")
                    st.caption("Comment (API):")
                    st.code(last_comment or "(empty)", language="text")
                    # Cleanup + redirect
                    st.session_state.pop("add_char_code", None)
                    st.session_state.pop("add_char_exp", None)
                    st.session_state["account_view"] = "profile"
                    st.rerun()
                else:
                    st.error("Verification failed. Make sure the code is in your character comment and not expired.")
                    if last_comment is not None:
                        st.caption("Comment received from API (for reference):")
                        st.code(last_comment or "(empty)", language="text")
                    st.caption("Note: TibiaData may take a couple of minutes to reflect changes to the comment.")


    st.button("← Back to Profile", on_click=on_back, type="secondary")
