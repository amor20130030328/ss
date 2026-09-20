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

import os

# 全局异步HTTP客户端（复用连接池）
_http_client = None

def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(
                max_connections=100,      # 允许100个并发连接
                max_keepalive_connections=0  # 禁用keepalive，每次新建连接
            ),
            http2=True  # 启用HTTP/2（如果服务端支持）
        )
        logger.info(f"HTTP客户端初始化完成，连接池大小=100, keepalive=0（禁用连接复用）")
    return _http_client


async def request_speaker_omni(
        session_id: str,
        data: np.ndarray,
        asr: str,
        vad_start: str,
) -> dict:
    start_time = time.time()
    request_id = str(uuid.uuid4())

    # 直接在主线程编码，numpy tobytes() 已经很快了
    encode_start = time.time()
    wave_bytes = data.tobytes()
    wave_b64 = base64.b64encode(wave_bytes).decode('utf-8')
    encode_time = time.time() - encode_start
    logger.info(f"[request_speaker_omni] Base64编码耗时={encode_time:.3f}s, 数据大小={len(wave_bytes)/1024:.1f}KB")

    payload = {
        "data": wave_b64,
        "asr": asr,
        "vad_start": vad_start,
        "session_id": session_id,
    }
    data, headers = build_mep_request(payload, config.speaker_omni_bid, config.speaker_omni_flowId)
    logger.info(f"[request_speaker_omni] 开始请求 session_id={session_id}, url={config.omni_address}")

    api_start = time.time()
    result = await common_api_call(request_id, config.omni_address, headers, data, 3, api_name="speaker_omni")
    api_time = time.time() - api_start

    response_data = result.get("src", {}) if result else {}
    elapsed = time.time() - start_time
    logger.info(f"[request_speaker_omni] 完成 session_id={session_id}, 总耗时={elapsed:.3f}s (编码={encode_time:.3f}s, API={api_time:.3f}s), 返回={'有' if response_data else '无'}")
    return response_data




async def request_qwen3_asr(
        session_id: str,
        data: np.ndarray,
        prev : str,
        enable_fa: bool = False
) -> dict:
    request_id = session_id

    # 直接在主线程编码，numpy tobytes() 已经很快了
    encode_start = time.time()
    wave_bytes = data.tobytes()
    wave_b64 = base64.b64encode(wave_bytes).decode('utf-8')
    encode_time = time.time() - encode_start
    logger.debug(f"[request_qwen3_asr] Base64编码耗时={encode_time:.3f}s, 数据大小={len(wave_bytes)/1024:.1f}KB")

    payload = {
        "data": wave_b64,
        "session_id": session_id,
        "prev_src": prev,
    }

    if enable_fa:
        payload["enable_fa"] = "true"
    data, headers = build_mep_request(payload, config.qwen3_asr_bid, config.qwen3_asr_flowId)
    logger.info(f"[request_qwen3_asr] 开始请求 session_id={session_id}, enable_fa={enable_fa}, url={config.omni_address}")
    result = await common_api_call(request_id, config.omni_address, headers, data, 3, api_name="qwen3_asr")
    response_data = result.get("src", {}) if result else {}
    logger.info(f"[request_qwen3_asr] 请求完成 session_id={session_id}, 返回数据={'有' if response_data else '无'}")
    return response_data


async def common_api_call(
        request_id: str,
        url: str,
        headers: dict,
        data: dict,
        timeout: int,
        api_name: str = "unknown"
) -> dict:
    """
    通用API调用函数 - 异步版本（每次创建独立客户端避免HTTP/1.1连接复用问题）
    """
    # 每次创建独立客户端，避免连接复用导致的排队
    client = httpx.AsyncClient(timeout=timeout)

    try:
        # 记录请求开始时间
        req_start = time.time()
        logger.debug(f"[common_api_call:{api_name}] 发起请求 request_id={request_id}, url={url}, timeout={timeout}")

        response = await client.post(url, headers=headers, content=json.dumps(data), timeout=timeout)

        # 记录网络耗时
        network_time = time.time() - req_start
        logger.info(f"[common_api_call:{api_name}] 网络请求完成 request_id={request_id}, 网络耗时={network_time:.3f}s, status={response.status_code}")

        # 记录JSON解析时间
        parse_start = time.time()
        result = response.json()
        parse_time = time.time() - parse_start
        logger.debug(f"[common_api_call:{api_name}] JSON解析耗时={parse_time:.3f}s")

        if result['result'] and result['result']['code'] == '0':
            return result['result']['content'][0]
        else:
            logger.warning(f"API call returned non-success code for {request_id}: {result.get('result', {})}")
            return {}
    except httpx.TimeoutException as e:
        logger.error(f"API call timeout for {request_id} after {timeout}s: {e}")
        return {}
    except httpx.HTTPStatusError as e:
        logger.error(f"API call HTTP error for {request_id}: status={e.response.status_code}, body={e.response.text[:200]}")
        return {}
    except Exception as e:
        logger.error(f"API call failed for {request_id}: {type(e).__name__}: {e}", exc_info=True)
        return {}
    finally:
        # 关闭独立客户端
        await client.aclose()


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

