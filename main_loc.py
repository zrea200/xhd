from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import xml.etree.ElementTree as ET
import time
from wechatpy.crypto import WeChatCrypto
from typing import Dict, Any
from hashlib import sha1
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置信息
TOKEN = "KStRJyYrF3ApFxvX7CHaL"
ENCODING_AES_KEY = "BbXGJfvbsjzEuKL3sDtVSIWhCo7UUf8sYSjrQPwn5A0"
CORP_ID = "ww675f6f1bb032977f"

app = FastAPI(title="企业微信智能机器人后台")

# 跨域中间件（开发环境使用，生产环境建议限制来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_signature(msg_signature: str, timestamp: str, nonce: str, token: str) -> bool:
    """验证企业微信消息签名"""
    try:
        tmp_list = [token, timestamp, nonce]
        tmp_list.sort()
        tmp_str = ''.join(tmp_list).encode('utf-8')
        signature = sha1(tmp_str).hexdigest()
        return signature == msg_signature
    except Exception as e:
        logger.error(f"签名验证异常: {str(e)}")
        return False


def decrypt_message(encrypt_msg: str, msg_signature: str, timestamp: str, nonce: str) -> str:
    """解密企业微信加密消息"""
    try:
        crypto = WeChatCrypto(TOKEN, ENCODING_AES_KEY, CORP_ID)
        ret, decrypted_msg = crypto.decrypt_message(encrypt_msg, msg_signature, timestamp, nonce)
        if ret != 0:
            raise Exception(f"解密失败，错误码: {ret}")
        return decrypted_msg
    except Exception as e:
        logger.error(f"消息解密异常: {str(e)}")
        raise


def encrypt_message(reply_xml: str, nonce: str, timestamp: str) -> str:
    """加密企业微信回复消息"""
    try:
        crypto = WeChatCrypto(TOKEN, ENCODING_AES_KEY, CORP_ID)
        ret, encrypted_msg = crypto.encrypt_message(reply_xml, nonce, timestamp)
        if ret != 0:
            raise Exception(f"加密失败，错误码: {ret}")
        return encrypted_msg
    except Exception as e:
        logger.error(f"消息加密异常: {str(e)}")
        raise


@app.get("/wechat/robot/callback")
async def verify_url(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str
):
    """验证回调URL有效性（企业微信首次配置时调用）"""
    try:
        # 验证签名
        if not verify_signature(msg_signature, timestamp, nonce, TOKEN):
            logger.warning("URL验证签名失败")
            return Response("签名验证失败", status_code=400)
        
        # 解密echostr
        decrypted_echostr = decrypt_message(echostr, msg_signature, timestamp, nonce)
        
        # 解析解密后的XML，提取Msg字段（企业微信要求返回明文）
        root = ET.fromstring(decrypted_echostr)
        msg = root.find("Msg").text if root.find("Msg") is not None else decrypted_echostr
        
        logger.info("URL验证成功")
        return Response(msg, media_type="text/plain")
    except Exception as e:
        logger.error(f"URL验证异常: {str(e)}")
        return Response(f"验证失败: {str(e)}", status_code=500)


@app.post("/wechat/robot/callback")
async def handle_robot_message(request: Request):
    """处理企业微信机器人回调的消息"""
    try:
        # 获取请求参数
        query_params = request.query_params
        msg_signature = query_params.get("msg_signature")
        timestamp = query_params.get("timestamp")
        nonce = query_params.get("nonce")
        
        if not all([msg_signature, timestamp, nonce]):
            logger.warning("请求参数缺失")
            return Response("参数缺失", status_code=400)
        
        # 读取加密消息体
        body = await request.body()
        xml_data = body.decode("utf-8")
        logger.debug(f"收到加密消息: {xml_data}")
        
        # 提取Encrypt字段
        try:
            encrypt = ET.fromstring(xml_data).find("Encrypt").text
        except ET.ParseError:
            logger.error("XML解析失败")
            return Response("消息格式错误", status_code=400)
        
        # 解密消息
        decrypted_xml = decrypt_message(encrypt, msg_signature, timestamp, nonce)
        logger.debug(f"解密后消息: {decrypted_xml}")
        
        # 解析消息内容
        try:
            msg_root = ET.fromstring(decrypted_xml)
            msg_type = msg_root.find("MsgType").text
            from_user = msg_root.find("FromUserName").text
            to_user = msg_root.find("ToUserName").text
        except Exception as e:
            logger.error(f"消息解析失败: {str(e)}")
            return Response("消息解析失败", status_code=400)
        
        # 处理不同类型的消息
        reply_content = handle_message_type(msg_type, msg_root)
        logger.info(f"生成回复内容: {reply_content}")
        
        # 构造回复XML
        reply_xml = generate_reply_xml(to_user, from_user, "text", reply_content)
        
        # 加密回复消息
        encrypted_reply = encrypt_message(reply_xml, nonce, timestamp)
        logger.debug(f"加密后回复: {encrypted_reply}")
        
        return Response(encrypted_reply, media_type="text/plain")
    
    except Exception as e:
        logger.error(f"处理消息异常: {str(e)}")
        return Response("服务器内部错误", status_code=500)


def handle_message_type(msg_type: str, msg_root: ET.Element) -> str:
    """处理不同类型的消息，返回回复内容"""
    try:
        if msg_type == "text":
            content = msg_root.find("Content").text
            return f"收到文本消息: {content}"
        
        elif msg_type == "image":
            media_id = msg_root.find("MediaId").text
            pic_url = msg_root.find("PicUrl").text
            return f"收到图片，MediaID: {media_id}, 图片地址: {pic_url}"
        
        elif msg_type == "news":
            articles = []
            for article in msg_root.findall("Articles/Article"):
                title = article.find("Title").text
                url = article.find("Url").text
                articles.append(f"标题: {title}, 链接: {url}")
            return f"收到图文消息，共{len(articles)}篇\n" + "\n".join(articles)
        
        else:
            return f"暂不支持的消息类型: {msg_type}"
    except Exception as e:
        logger.error(f"消息处理异常: {str(e)}")
        return "消息处理失败"


def generate_reply_xml(to_user: str, from_user: str, msg_type: str, content: str) -> str:
    """生成回复消息的XML"""
    create_time = int(time.time())
    return f"""
    <xml>
        <ToUserName><![CDATA[{to_user}]]></ToUserName>
        <FromUserName><![CDATA[{from_user}]]></FromUserName>
        <CreateTime>{create_time}</CreateTime>
        <MsgType><![CDATA[{msg_type}]]></MsgType>
        <Content><![CDATA[{content}]]></Content>
    </xml>
    """.strip()