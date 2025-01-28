# auth.py
import streamlit as st

def login(username, password):
    # Dummy user credentials (bisa diganti dengan database)
    valid_users = {
        "admin": "1234",
        "user1": "password",
    }
    if username in valid_users and valid_users[username] == password:
        return True
    return False

def logout():
    # Reset session state untuk logout
    st.session_state["authenticated"] = False
