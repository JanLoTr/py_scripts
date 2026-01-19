# app.py
import streamlit as st
import groq
import os

# Titel der App
st.title("Groq Chat App")

# API Key aus Umgebungsvariablen laden
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("GROQ_API_KEY Umgebungsvariable nicht gefunden!")
    st.stop()

# Groq Client initialisieren
client = groq.Client(api_key=api_key)

# Chat-Interface
st.subheader("Chat mit Groq")

# Chatverlauf in Session State speichern
if "messages" not in st.session_state:
    st.session_state.messages = []

# Vorherige Nachrichten anzeigen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Eingabefeld für neue Nachricht
if prompt := st.chat_input("Wie kann ich helfen?"):
    # Benutzernachricht hinzufügen
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Benutzernachricht anzeigen
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Antwort von Groq holen
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # Streamen der Antwort
            stream = client.chat.completions.create(
                model="mixtral-8x7b-32768",  # oder ein anderes Modell
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            st.error(f"Fehler: {e}")
            full_response = "Entschuldigung, ein Fehler ist aufgetreten."
    
    # Assistant-Nachricht zum Verlauf hinzufügen
    st.session_state.messages.append({"role": "assistant", "content": full_response})