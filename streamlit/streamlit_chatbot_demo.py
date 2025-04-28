import streamlit as st
import json
import random
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile
import os
from datetime import datetime, timedelta
from transformers import pipeline
 
# Load Hugging Face zero-shot classifier
classifier = pipeline("zero-shot-classification")
 
# Load project data
base_path = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_path, "Data.json")
 
with open(file_path, "r") as f:
    data = json.load(f)
 
teams = data["teams"]
 
# Utility functions
def get_team_by_name(name):
    return next((t for t in teams if t["team_name"].lower() == name.lower()), None)
 
def get_latest_sprint(team):
    return team["sprints"][-1]
 
def get_last_n_velocities(team, n=3):
    return [s["velocity"] for s in team["sprints"][-n:]]
 
def calculate_risk(team):
    latest = get_latest_sprint(team)
    risk_score = 0
    if latest["blockers"] >= 4:
        risk_score += 1
    if latest["story_points_completed"] < 0.8 * latest["story_points_planned"]:
        risk_score += 1
    if latest["bugs_reported"] > 4:
        risk_score += 1
    return "🔴 High Risk" if risk_score >= 2 else "🟡 Moderate Risk" if risk_score == 1 else "🟢 Low Risk"
 
def get_teams_with_recent_sprint(days=7):
    recent_teams = []
    today = datetime.today()
    cutoff = today - timedelta(days=days)
    for team in teams:
        last_sprint = get_latest_sprint(team)
        end_date = last_sprint.get("end_date")
        if end_date:
            sprint_date = datetime.strptime(end_date, "%Y-%m-%d")
            if sprint_date >= cutoff:
                recent_teams.append(team)
    return recent_teams
 
# Prediction function
def predict_next_sprint(team, lookback=3):
    sprints = team["sprints"][-lookback:]
    avg_velocity = int(sum(s["velocity"] for s in sprints) / len(sprints))
    avg_blockers = round(sum(s["blockers"] for s in sprints) / len(sprints), 1)
    avg_bugs = round(sum(s["bugs_reported"] for s in sprints) / len(sprints), 1)
    predicted_velocity = avg_velocity + random.randint(-2, 2)
    predicted_blockers = max(0, avg_blockers + random.uniform(-1, 1))
    predicted_bugs = max(0, avg_bugs + random.uniform(-1, 1))
    return predicted_velocity, round(predicted_blockers, 1), round(predicted_bugs, 1)
 
# Plot functions
def plot_velocity(team):
    sprints = team["sprints"]
    x = [f"Sprint {s['sprint_id']}" for s in sprints]
    y = [s["velocity"] for s in sprints]
    fig, ax = plt.subplots()
    ax.plot(x, y, marker='o', linewidth=2)
    ax.set_title(f"Velocity Over Time – {team['team_name']}")
    ax.set_ylabel("Story Points")
    ax.set_xlabel("Sprint")
    ax.grid(True)
    st.pyplot(fig)
 
def plot_blockers_bugs(team):
    sprints = team["sprints"]
    x = [f"Sprint {s['sprint_id']}" for s in sprints]
    blockers = [s["blockers"] for s in sprints]
    bugs = [s["bugs_reported"] for s in sprints]
    fig, ax = plt.subplots()
    ax.bar(x, blockers, label="Blockers", alpha=0.7)
    ax.bar(x, bugs, bottom=blockers, label="Bugs", alpha=0.7)
    ax.set_title(f"Blockers & Bugs – {team['team_name']}")
    ax.set_ylabel("Count")
    ax.set_xlabel("Sprint")
    ax.legend()
    st.pyplot(fig)
 
def plot_completion_ratio(team):
    sprints = team["sprints"]
    x = [f"Sprint {s['sprint_id']}" for s in sprints]
    completed = [s["story_points_completed"] for s in sprints]
    planned = [s["story_points_planned"] for s in sprints]
    fig, ax = plt.subplots()
    ax.plot(x, completed, label="Completed", marker='o')
    ax.plot(x, planned, label="Planned", linestyle='--', marker='x')
    ax.set_title(f"Planned vs Completed – {team['team_name']}")
    ax.set_ylabel("Story Points")
    ax.set_xlabel("Sprint")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)
 
# PDF Export
def export_pdf_report(team):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_file.name, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"DevOps Sprint Report – {team['team_name']}")
    latest = get_latest_sprint(team)
    text = f"""
    Sprint ID: {latest['sprint_id']}
    Planned Story Points: {latest['story_points_planned']}
    Completed Story Points: {latest['story_points_completed']}
    Velocity: {latest['velocity']}
    Blockers: {latest['blockers']}
    Bugs Reported: {latest['bugs_reported']}
    Risk Level: {calculate_risk(team)}
    """
    c.setFont("Helvetica", 11)
    y = height - 100
    for line in text.strip().split("\n"):
        c.drawString(50, y, line.strip())
        y -= 20
    c.showPage()
    c.save()
    return temp_file.name
 
# Intent Detection + Chatbot Logic
def detect_intent(user_input):
    candidate_labels = [
        "sprint status", "user story assignment", "user story duration", "bug tracking",
        "sprint prediction", "team members", "list teams", "export report"
    ]
    result = classifier(user_input, candidate_labels)
    return result['labels'][0], result['scores'][0]
 
def generate_response_with_nlp(user_input):
    intent, score = detect_intent(user_input)
    user_input_lower = user_input.lower()
 
    if score < 0.7:
        return "I'm not quite sure what you mean. Can you rephrase?", None
 
    if intent == "list teams":
        return "📋 Here are the available teams: " + ", ".join([t["team_name"] for t in teams]), None
 
    if intent == "user story assignment":
        for team in teams:
            for story in team.get("user_stories", []):
                if story["id"].lower() in user_input_lower:
                    return f"🧠 User story **{story['id']}** is assigned to **{story['assigned_to']}** in Team {team['team_name']}.", None
        return "❓ I couldn’t find that user story ID.", None
 
    if intent == "user story duration":
        for team in teams:
            for story in team.get("user_stories", []):
                if story["id"].lower() in user_input_lower:
                    opened_date = datetime.strptime(story["opened_date"], "%Y-%m-%d")
                    days_open = (datetime.today() - opened_date).days
                    return f"⏳ User story **{story['id']}** has been open for **{days_open} days**.", None
        return "❓ I couldn’t find that user story ID.", None
 
    if intent == "bug tracking":
        for team in teams:
            if team["team_name"].lower() in user_input_lower:
                bugs = team.get("bugs", [])
                open_bugs = [b for b in bugs if b["status"].lower() == "open"]
                closed_bugs = [b for b in bugs if b["status"].lower() == "closed"]
                return (
                    f"🐞 Bug Tracker for Team {team['team_name']}:\n"
                    f"- Open: {len(open_bugs)}\n"
                    f"- Closed: {len(closed_bugs)}\n"
                    f"Keep squashing them! 💪",
                    None
                )
 
    for team in teams:
        name = team["team_name"].lower()
        if name in user_input_lower:
            if intent == "sprint status":
                sprint = get_latest_sprint(team)
                response = (
                    f"📊 *Sprint Overview for {team['team_name']} (Sprint {sprint['sprint_id']})*\n\n"
                    f"🗂️ Planned: {sprint['story_points_planned']} SP\n"
                    f"✅ Completed: {sprint['story_points_completed']} SP\n"
                    f"⚡ Velocity: {sprint['velocity']}\n"
                    f"🪤 Blockers: {sprint['blockers']} | 🐞 Bugs: {sprint['bugs_reported']}\n"
                    f"🚦 Risk Level: {calculate_risk(team)}"
                )
                return response, None
 
            elif intent == "sprint prediction":
                predicted_velocity, predicted_blockers, predicted_bugs = predict_next_sprint(team)
                return (
                    f"🔮 *Sprint Forecast for {team['team_name']}*\n\n"
                    f"- **Predicted Velocity**: {predicted_velocity} SP\n"
                    f"- **Expected Blockers**: {predicted_blockers}\n"
                    f"- **Expected Bugs**: {predicted_bugs}\n\n"
                    f"Plan accordingly and let's aim high! 🚀",
                    None
                )
 
            elif intent == "team members":
                members = [f"👤 {m['name']} – *{m['role']}*" for m in team["members"]]
                return f"👥 Here's the lineup for Team {team['team_name']}:\n" + "\n".join(members), None
 
    return "🤔 Not sure how to help with that yet. Try asking something else?", None
 
# Streamlit UI
st.set_page_config(page_title="DevOps Copilot", layout="centered")
st.title("🤖 DevOps Assistant – Sprint Intelligence Demo")
 
st.markdown("Ask questions like:")
st.markdown("- *What is the sprint status of Team Alpha*")
st.markdown("- *How should Team Alpha's next sprint look like?*")
st.markdown("- *How long has US-101 been open?*")
st.markdown("- *What is the bug progress for Team Gamma?*")
 
user_input = st.text_input("Ask something:", "")
 
if user_input:
    st.markdown("🧠 Thinking...")
    reply, chart_team = generate_response_with_nlp(user_input)
    st.markdown(f"**Assistant:**\n\n{reply}")
 
    if chart_team:
        plot_velocity(chart_team)
        plot_blockers_bugs(chart_team)
        plot_completion_ratio(chart_team)
 
# PDF Export
with st.expander("📄 Export Sprint Report"):
    team_names = [t["team_name"] for t in teams]
    selected_team = st.selectbox("Select a team", team_names)
    if st.button("Export Report as PDF"):
        team_obj = get_team_by_name(selected_team)
        if team_obj:
            pdf_path = export_pdf_report(team_obj)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="📥 Download Sprint Report",
                    data=f,
                    file_name=f"{selected_team}_Sprint_Report.pdf",
                    mime="application/pdf"
                )
            os.remove(pdf_path)
 
# Auto-generate weekly reports
with st.expander("🗓️ Auto-Generate Weekly Reports"):
    st.markdown("This generates reports for teams whose sprints ended in the last 7 days.")
    if st.button("Generate Weekly Reports"):
        recent_teams = get_teams_with_recent_sprint()
        if not recent_teams:
            st.info("No teams had sprints ending this week.")
        else:
            for team in recent_teams:
                pdf_path = export_pdf_report(team)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download {team['team_name']} Sprint Report",
                        data=f,
                        file_name=f"{team['team_name']}_Sprint_Report.pdf",
                        mime="application/pdf"
                    )
                os.remove(pdf_path)
