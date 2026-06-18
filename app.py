import streamlit as st

from src.database import init_database
from src.ui.deps import CHROMA_AVAILABLE, RAG_IMPORTS_OK, purge_orphaned_chunks
from src.ui.pages.dashboard import render_dashboard
from src.ui.pages.file_explorer import render_file_explorer
from src.ui.pages.ingestion import render_ingestion
from src.ui.pages.operations import render_operations
from src.ui.pages.questions import render_questions
from src.ui.pages.reports import render_reports
from src.ui.rag_helpers import _chroma_dir
from src.ui.sidebar import render_sidebar
from src.ui.state import init_state
from src.ui.styles import inject_css

st.set_page_config(
    page_title="INSIGHT.AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    inject_css()
    init_state()
    render_sidebar()
    init_database(st.session_state.db_path)
    if RAG_IMPORTS_OK and CHROMA_AVAILABLE and not st.session_state._chroma_purged:
        st.session_state._chroma_purged = True
        purge_orphaned_chunks(st.session_state.db_path, persist_dir=_chroma_dir())

    page = st.session_state.page
    if page == "Ask Questions":
        render_questions()
    elif page == "Ingestion Hub":
        render_ingestion()
    elif page == "Executive Dashboard":
        render_dashboard()
    elif page == "File Explorer":
        render_file_explorer()
    elif page == "Operations & Recovery":
        render_operations()
    elif page == "Reports and Logs":
        render_reports()


if __name__ == "__main__":
    main()
