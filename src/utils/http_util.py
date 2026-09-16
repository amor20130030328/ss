import base64
import hashlib
import hmac
import json
import time
import uuid

import numpy as np
import httpx

from src.configs.config import config
from src.utils.crypt_util import decrypt_secret
from src.logger.logger_adapter import logger

# 全局异步HTTP客户端（复用连接池）
_http_client = None

def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
    return _http_client


async def request_speaker_omni(
        session_id: str,
        data: np.ndarray,
        asr: str,
        vad_start: str,
) -> dict:
    start_time = time.time()
    request_id = str(uuid.uuid4())
    wave_b64 = base64.b64encode(data.tobytes()).decode('utf-8')
    payload = {
        "data": wave_b64,
        "asr": asr,
        "vad_start": vad_start,
        "session_id": session_id,
    }
    data, headers = build_mep_request(payload, config.speaker_omni_bid, config.speaker_omni_flowId)
    logger.info(f"[request_speaker_omni] 开始请求 session_id={session_id}, url={config.omni_address}")
    result = await common_api_call(request_id, config.omni_address, headers, data, 3)
    response_data = result.get("src", {}) if result else {}
    elapsed = time.time() - start_time
    logger.info(f"[request_speaker_omni] 请求完成 session_id={session_id}, 耗时={elapsed:.3f}s, 返回数据={'有' if response_data else '无'}")
    return response_data




async def request_qwen3_asr(
        session_id: str,
        data: np.ndarray,
        prev : str,
        enable_fa: bool = False
) -> dict:
    request_id = session_id
    wave_b64 = base64.b64encode(data.tobytes()).decode('utf-8')
    payload = {
        "data": wave_b64,
        "session_id": session_id,
        "prev_src": prev,
    }

    if enable_fa:
        payload["enable_fa"] = "true"
    data, headers = build_mep_request(payload, config.qwen3_asr_bid, config.qwen3_asr_flowId)
    logger.info(f"[request_qwen3_asr] 开始请求 session_id={session_id}, enable_fa={enable_fa}, url={config.omni_address}")
    result = await common_api_call(request_id, config.omni_address, headers, data, 3)
    response_data = result.get("src", {}) if result else {}
    logger.info(f"[request_qwen3_asr] 请求完成 session_id={session_id}, 返回数据={'有' if response_data else '无'}")
    return response_data


async def common_api_call(
        request_id: str,
        url: str,
        headers: dict,
        data: dict,
        timeout: int
) -> dict:
    """
    通用API调用函数 - 异步版本
    """
    try:
        client = get_http_client()
        response = await client.post(url, headers=headers, content=json.dumps(data), timeout=timeout)
        result = response.json()
        if result['result'] and result['result']['code'] == '0':
            return result['result']['content'][0]
        else:
            logger.warning(f"API call returned non-success code for {request_id}: {result.get('result', {})}")
            return {}
    except Exception as e:
        logger.error(f"API call failed for {request_id}: {e}", exc_info=True)
        return {}


def build_mep_request(payload, bId, flowId) -> tuple[dict, dict]:
    app_id = config.mep_app_id
    sign_key = decrypt_secret(config.mep_sign_key)

    data = {
        'data': payload,
        "meta": {
            "bId": f"{bId}",
            "flowId": f"{flowId}"
        },
        "version": "1.0"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": calc_mep_sign(json.dumps(data), sign_key, app_id)
    }
    return data, headers


def calc_mep_sign(data, sign_key, app_id):
    payload = ""
    if data is not None and data != "" and len(data) > 0:
        payload += data
    query_str = ""
    path_str = ""
    query_str = query_str[:-1]
    for v in ["service"]:
        path_str += "/{}".format(v)
    timestamp = int(time.time() * 1000)
    sign_str = "{}&{}&{}&{}&appid={}&timestamp={}".format(
        "POST", path_str, query_str, data, app_id, timestamp)
    sign_key = sign_key.encode('utf-8')
    sign_str = sign_str.encode('utf-8')
    sign = base64.b64encode(hmac.new(
        sign_key, sign_str, digestmod=hashlib.sha256).digest()).decode("utf-8")
    return 'CLOUDSOA-HMAC-SHA256 appid={}, timestamp={}, signature="{}"'.format(app_id, timestamp, sign)

