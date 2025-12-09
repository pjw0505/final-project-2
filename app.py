# =======================================================
# app.py: 고전 예술 기록 및 멸실유산 발굴 에이전트
# =======================================================

import streamlit as st
from openai import OpenAI
import json
import os
import time

# -------------------------------------------------------
# 1. 클라이언트 초기화 함수 (API 키 로딩)
# -------------------------------------------------------

@st.cache_resource
def get_openai_client():
    """Streamlit Secrets에서 API 키를 읽어 OpenAI 클라이언트를 초기화합니다."""
    
    try:
        # 💥 주의: Secrets에 저장한 이름(예: MY_OPENAI_KEY)을 사용해야 합니다. 💥
        # 여기서는 기본 이름으로 가정하고, 만약 오류가 나면 Secrets 설정에서 키 이름을 확인해야 합니다.
        api_key = st.secrets["secrets"]["OPENAI_API_KEY"].strip() 
    except KeyError:
        st.error("오류: Streamlit Secrets에 [secrets] 섹션 또는 OPENAI_API_KEY가 누락되었습니다. Secrets 설정을 확인해주세요.")
        st.stop()
        
    if not api_key or not api_key.startswith("sk-"):
        st.error("오류: API 키 값이 유효하지 않습니다. Secrets에 올바른 키를 입력해주세요.")
        st.stop()
        
    return OpenAI(api_key=api_key)

# -------------------------------------------------------
# 2. Tool 함수 정의 (Mock API)
# -------------------------------------------------------

def get_heritage_text_record(location: str, structure_name: str) -> str:
    """ 역사 기록 텍스트를 검색하는 Tool (Mock) """
    time.sleep(1)
    if "홍길동" in structure_name:
        return json.dumps({
            "status": "success",
            "text_record": "홍길동 작가는 1920년대 초 일본에서 유학했으며, 당시 파리 화단의 추상적 경향에 영향을 받았으나, 귀국 후 실험적인 단색화를 주로 선보였다. 초기에는 채색화도 병행했으나, 후기에는 마포를 사용한 물성 위주 작업에 집중했다.",
            "exhibition_count": 5
        })
    return json.dumps({"status": "error", "text_record": f"'{structure_name}'에 대한 상세 기록을 찾을 수 없습니다."})

def generate_visualization_data(data: str, visualization_type: str) -> str:
    """ 분석된 데이터를 기반으로 시각화 JSON을 생성하는 Tool (Mock) """
    time.sleep(1.5)
    if "단색화" in data and visualization_type == "연표":
        return json.dumps({
            "status": "success",
            "visualization_type": "연표",
            "data": [
                {"year": 1920, "event": "일본 유학 및 서양 추상화 경향 접촉"},
                {"year": 1925, "event": "단색화 기법 실험 시작"},
                {"year": 1930, "event": "조선미술전람회에서 마포 질감 위주 작품 발표"}
            ]
        })
    return json.dumps({"status": "error", "message": "요청된 시각화 데이터를 생성할 수 없습니다."})


# -------------------------------------------------------
# 3. Tool 스키마 정의 및 딕셔너리
# -------------------------------------------------------
tools = [
    # get_heritage_text_record 스키마
    {"type": "function", "function": {"name": "get_heritage_text_record", "description": "작가나 유산의 이름으로 상세한 역사 기록 텍스트를 검색합니다.", "parameters": {"type": "object", "properties": {"location": {"type": "string"}, "structure_name": {"type": "string"}}, "required": ["structure_name"]}}},
    # generate_visualization_data 스키마
    {"type": "function", "function": {"name": "generate_visualization_data", "description": "분석된 텍스트를 기반으로 연표(timeline)나 차트(chart) 형태의 시각화 JSON 데이터를 생성합니다.", "parameters": {"type": "object", "properties": {"data": {"type": "string", "description": "분석할 텍스트 기록 전체"}, "visualization_type": {"type": "string", "description": "원하는 시각화 형식 (연표, 차트 등)"}}, "required": ["data", "visualization_type"]}}},
]
available_functions = {
    "get_heritage_text_record": get_heritage_text_record,
    "generate_visualization_data": generate_visualization_data,
}


# -------------------------------------------------------
# 4. 핵심 에이전트 실행 함수 (MCP 로직)
# -------------------------------------------------------

def run_master_agent(user_prompt: str, location: str, structure_name: str, viz_type: str):
    
    client = get_openai_client() # 클라이언트 객체 가져오기
    messages = [{"role": "user", "content": user_prompt}]
    tool_results = {}
    
    st.info("AI 에이전트가 요청을 분석하고 Tool 호출 계획을 수립합니다.")
    
    for i in range(3):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        
        response_message = response.choices[0].message
        if not response_message.tool_calls:
            return response_message.content, tool_results
        
        messages.append(response_message)
        
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            st.warning(f"STEP {i+1}: 🛠️ 에이전트가 Tool '{function_name}'을(를) 호출합니다.")
            
            # Tool 호출 시 필요한 인자 처리
            if function_name == "get_heritage_text_record":
                function_args['location'] = location
                function_args['structure_name'] = structure_name
            elif function_name == "generate_visualization_data":
                record = tool_results.get("get_heritage_text_record", {}).get("text_record", "")
                function_args['data'] = record
                function_args['visualization_type'] = viz_type
            
            function_response = available_functions[function_name](**function_args)
            
            tool_results[function_name] = json.loads(function_response)
            messages.append({"tool_call_id": tool_call.id, "role": "tool", "content": function_response})
            
    final_response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return final_response.choices[0].message.content, tool_results


# -------------------------------------------------------
# 5. Streamlit UI 및 실행 로직
# -------------------------------------------------------

st.title("📜 지역 문화유산 디지털 마스터 에이전트")
st.markdown("역사 기록을 분석하고 멸실된 유산의 배경을 시각화합니다.")

# 사이드바 (입력 영역)
with st.sidebar:
    st.header("문화유산 정보 입력")
    location = st.text_input("지역:", "서울 종로")
    structure_name = st.text_input("작가/유산 이름:", "홍길동 작가")
    
    viz_type = st.selectbox(
        "분석 시각화 형식:", 
        ['연표', '차트', '일반 분석']
    )
    
    prompt = st.text_area(
        "AI 분석 요청:", 
        f"'{structure_name}'의 역사 기록을 검색하고, 그 기록을 바탕으로 주요 활동 시기를 '{viz_type}' 형식으로 시각화할 수 있도록 분석해 줘.",
        height=150
    )

# 메인 실행 버튼
if st.button("🔎 분석 및 시각화 실행"): 
    if structure_name and prompt:
        with st.spinner("AI 에이전트가 기록 검색 및 시각화 명령을 진행 중입니다..."):
            
            # run_master_agent 함수 호출
            analysis_text, tool_results = run_master_agent(prompt, location, structure_name, viz_type)
            
            # 결과 출력
            st.subheader("💡 에이전트 최종 분석 및 스토리텔링")
            st.write(analysis_text)
            
            if "get_heritage_text_record" in tool_results:
                record = tool_results["get_heritage_text_record"]
                if record.get("status") == "success":
                    st.subheader("📜 검색된 원본 역사 기록")
                    st.code(record["text_record"], language='markdown')
            
            if "generate_visualization_data" in tool_results:
                viz_data = tool_results["generate_visualization_data"]
                if viz_data.get("status") == "success" and viz_data.get("visualization_type") == "연표":
                    st.subheader("📊 활동 연표 시각화 결과")
                    try:
                        import pandas as pd
                        df = pd.DataFrame(viz_data["data"])
                        st.dataframe(df, use_container_width=True)
                    except ImportError:
                        st.write(viz_data["data"])
                    st.markdown("_(실제 프로젝트에서는 Plotly/Altair를 사용하여 인터랙티브한 그래프를 여기에 표시할 수 있습니다.)_")

    else:
        st.warning("작가/유산 이름과 분석 요청을 입력해 주세요.")
