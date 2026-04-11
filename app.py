import streamlit as st

st.title("Simple Calculator")

if 'expression' not in st.session_state:
    st.session_state.expression = " "
if 'result' not in st.session_state:
    st.session_state.result = " "
def add_to_expression(char):
    st.session_state.expression += char
def clear():
    st.session_state.expression = " "
    st.session_state.result = " "
def calculate():
    try:
        st.session_state.result = str(eval(st.session_state.expression))
    except:
        st.session_state.result = "Error"
st.text_input("Expression",value = st.session_state.expression)
st.text_input("Result",value=st.session_state.result)

col1,col2,col3,col4 = st.columns(4)

with col1:
    if st.button("7"):
        add_to_expression("7")
    if st.button("4"):
        add_to_expression("4")
    if st.button("1"):
        add_to_expression("1")
    if st.button("0"):
        add_to_expression("0")

with col2:
    if st.button("8"):
        add_to_expression("8")
    if st.button("5"):
        add_to_expression("5")
    if st.button("2"):
        add_to_expression("2")
    if st.button("."):
        add_to_expression(".")

with col3:
    if st.button("9"):
        add_to_expression("9")
    if st.button("6"):
        add_to_expression("6")
    if st.button("3"):
        add_to_expression("3")
    if st.button("="):
        calculate()
    
with col4:
    if st.button("/"):
        add_to_expression("/")
    if st.button("*"):
        add_to_expression("*")
    if st.button("-"):
        add_to_expression("-")
    if st.button("+"):
        add_to_expression("+")
    if st.button("C"):
        clear()