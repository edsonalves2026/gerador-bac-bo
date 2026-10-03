"""Modal de Nova Estratégia Personalizada (inspirado no print de referência)."""
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# =============================================================================
# HELPERS DE COR / EMOJI
# =============================================================================
CORES_VALIDAS = ("🔴", "🔵", "🟡")

CORES_EMOJI = {
    "🔴": "B",
    "🔵": "P",
    "🟡": "T",
}

CORES_HEX = {
    "🔴": "#ef4444",
    "🔵": "#3b82f6",
    "🟡": "#eab308",
}

ENTRADAS_ESPECIAIS = {
    "PLAYER-E": "🔵",
    "BANKER-E": "🔴",
}


# =============================================================================
# STATE
# =============================================================================
def _init_state() -> None:
    defaults = {
        "_modal_open": False,
        "_padrao_temp": [],       # lista de cores OU strings "🔴 8"
        "_numero_temp": "",       # número opcional
        "_entrada_especial_temp": None,
        "_nome_temp": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_state() -> None:
    st.session_state["_padrao_temp"] = []
    st.session_state["_numero_temp"] = ""
    st.session_state["_entrada_especial_temp"] = None
    st.session_state["_nome_temp"] = ""


# =============================================================================
# COMPONENTE PRINCIPAL
# =============================================================================
def render_estrategia_sidebar(worker) -> None:
    """
    Renderiza na sidebar:
      - Cabeçalho "🎯 Estratégia Personalizada" com botão ➕
      - Lista de estratégias existentes (chaves AUTO_* e manuais)
      - Modal (via st.dialog) quando o botão ➕ é clicado
    """
    _init_state()

    st.sidebar.divider()

    # Header com botão ➕
    col_title, col_btn = st.sidebar.columns([5, 1])
    col_title.markdown("#### 🎯 Estratégia Personalizada")
    if col_btn.button("➕", key="btn_add_estrategia", help="Nova estratégia"):
        st.session_state["_modal_open"] = True
        _reset_state()
        st.rerun()

    # Lista de estratégias já salvas
    state = worker.get_state()
    padroes = state.get("PADROES_MANUAIS_COMPOSTOS", {})

    if not padroes:
        st.sidebar.info(
            "Nenhuma estratégia personalizada criada ainda. "
            "Clique no **➕** para criar sua primeira estratégia."
        )
    else:
        for chave, item in list(padroes.items()):
            seq = item.get("padrao", [])
            sug = item.get("sugestao", "—")
            seq_str = " ".join(str(x) for x in seq) if seq else "—"

            cols = st.sidebar.columns([5, 1])
            with cols[0]:
                st.markdown(
                    f"<div style='font-size:12px;line-height:1.3;color:#ddd'>"
                    f"<b>{chave}</b><br>"
                    f"<span style='letter-spacing:1px'>{seq_str}</span> "
                    f"→ <b>{sug}</b>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                key_hash = abs(hash(chave)) % 10_000_000
                if st.button("🗑️", key=f"del_estr_{key_hash}",
                             help=f"Remover {chave}"):
                    worker.remover_padrao(chave)
                    st.rerun()

    # Modal (só renderiza se aberto)
    if st.session_state.get("_modal_open"):
        _render_modal(worker)


# =============================================================================
# MODAL — Nova Estratégia
# =============================================================================
@st.dialog("🎯 Nova Estratégia Personalizada", width="large")
def _render_modal(worker) -> None:
    """Modal em estilo da imagem de referência."""
    _init_state()

    # ---- Nome ----
    st.markdown("#### 🏷️ Nome da Estratégia")
    nome = st.text_input(
        "Digite o nome da estratégia",
        value=st.session_state["_nome_temp"],
        label_visibility="collapsed",
        placeholder="Digite o nome da estratégia",
        key="modal_nome_input",
    )
    st.session_state["_nome_temp"] = nome

    # ---- Adicionar ao Padrão ----
    st.markdown("#### 🎯 Adicionar ao Padrão")
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        if st.button("🔴\n**B**", key="btn_cor_red", use_container_width=True):
            st.session_state["_padrao_temp"].append("🔴")
            st.rerun()
    with c2:
        if st.button("🔵\n**P**", key="btn_cor_blue", use_container_width=True):
            st.session_state["_padrao_temp"].append("🔵")
            st.rerun()
    with c3:
        if st.button("🟡\n**T**", key="btn_cor_tie", use_container_width=True):
            st.session_state["_padrao_temp"].append("🟡")
            st.rerun()
    with c4:
        if st.button("🟦\n**Player-E**", key="btn_player_e",
                     use_container_width=True, help="Player Especial"):
            st.session_state["_entrada_especial_temp"] = "PLAYER-E"
            st.rerun()
    with c5:
        if st.button("🟥\n**Banker-E**", key="btn_banker_e",
                     use_container_width=True, help="Banker Especial"):
            st.session_state["_entrada_especial_temp"] = "BANKER-E"
            st.rerun()

    # ---- Número opcional ----
    st.markdown("#### # Número (opcional)")
    numero = st.text_input(
        "Ex: 8",
        value=st.session_state["_numero_temp"],
        label_visibility="collapsed",
        placeholder="Ex: 8",
        key="modal_numero_input",
    )
    st.session_state["_numero_temp"] = numero

    # ---- Preview ----
    st.markdown("#### 👁️ Preview do Padrão")
    preview = _montar_preview()
    if preview:
        st.success(preview)
    else:
        st.caption(
            "ℹ️ Clique nos botões acima para criar seu padrão"
        )

    st.divider()

    # ---- Ações ----
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("⬅️ Remover Último", use_container_width=True):
            if st.session_state["_padrao_temp"]:
                st.session_state["_padrao_temp"].pop()
                st.rerun()
    with col2:
        if st.button("✖️ Cancelar", use_container_width=True):
            st.session_state["_modal_open"] = False
            _reset_state()
            st.rerun()
    with col3:
        if st.button("💾 Salvar Estratégia", type="primary",
                     use_container_width=True):
            ok, msg = _salvar(worker)
            if ok:
                st.session_state["_modal_open"] = False
                _reset_state()
                st.toast(msg, icon="✅")
                st.rerun()
            else:
                st.error(msg)


# =============================================================================
# HELPERS
# =============================================================================
def _montar_preview() -> str:
    partes = list(st.session_state["_padrao_temp"])
    if st.session_state["_numero_temp"]:
        partes.append(st.session_state["_numero_temp"])
    if st.session_state["_entrada_especial_temp"]:
        partes.append(f"[{st.session_state['_entrada_especial_temp']}]")
    return " ".join(str(x) for x in partes)


def _salvar(worker) -> Tuple[bool, str]:
    nome = (st.session_state["_nome_temp"] or "").strip()
    padrao = list(st.session_state["_padrao_temp"])
    numero = (st.session_state["_numero_temp"] or "").strip()
    especial = st.session_state["_entrada_especial_temp"]

    # Validações
    if not nome:
        return False, "⚠️ Digite um nome para a estratégia."
    if not padrao and not numero and not especial:
        return False, "⚠️ Adicione ao menos um elemento ao padrão."

    # Define sugestão
    if especial:
        sugestao = ENTRADAS_ESPECIAIS.get(especial, "🔴")
    else:
        # Sugestão padrão = última cor adicionada (o usuário pode editar depois)
        sugestao = padrao[-1] if padrao else "🔴"

    # Monta a sequência final
    sequencia: List[str] = list(padrao)
    if numero:
        if sequencia:
            sequencia[-1] = f"{sequencia[-1]} {numero}"
        else:
            sequencia.append(f"🔴 {numero}")
    if especial:
        sequencia.append(f"🔴 {especial}")

    # Salva via worker (persiste em SQLite)
    try:
        worker.add_padrao(nome, sequencia, sugestao)
        return True, f"Estratégia '{nome}' salva!"
    except Exception as e:
        return False, f"❌ Erro ao salvar: {e}"
