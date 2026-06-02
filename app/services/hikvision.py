"""
海康威视 ISAPI 协议服务层
基于 HTTP ISAPI 协议，无需安装 SDK，通过 requests 调用摄像头 CGI 接口。
支持：抓图、MJPEG 预览、云台控制、分辨率管理
"""
import time
import threading
from urllib.parse import urljoin
import requests
from requests.auth import HTTPDigestAuth


class HikvisionCamera:
    """海康摄像头 ISAPI 封装"""

    def __init__(self, base_url, username, password, timeout=10):
        """
        base_url: 如 http://192.168.1.64
        username: 摄像头用户名
        password: 摄像头密码
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.auth = HTTPDigestAuth(username, password)
        self._session = requests.Session()
        self._session.auth = self.auth
        self._ptz_session_id = None

    def _isapi(self, path):
        """拼接 ISAPI 完整 URL"""
        return urljoin(self.base_url + '/', path.lstrip('/'))

    def _check_connection(self):
        """检查摄像头连通性"""
        try:
            resp = self._session.get(
                self._isapi('/ISAPI/System/deviceInfo'),
                timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ==================== 抓图 ====================

    def capture(self):
        """
        截取当前帧，返回 (image_bytes, content_type)
        失败返回 (None, error_msg)
        """
        try:
            resp = self._session.get(
                self._isapi('/ISAPI/Streaming/channels/1/picture'),
                timeout=self.timeout
            )
            if resp.status_code == 200 and resp.content:
                content_type = resp.headers.get('Content-Type', 'image/jpeg')
                return resp.content, content_type
            return None, f"抓图失败: HTTP {resp.status_code}"
        except requests.RequestException as e:
            return None, str(e)

    def capture_to_file(self, file_path):
        """截取并保存到文件，返回 True/False"""
        img_bytes, error = self.capture()
        if img_bytes:
            with open(file_path, 'wb') as f:
                f.write(img_bytes)
            return True
        return False

    # ==================== MJPEG 预览 ====================

    def get_mjpeg_url(self, channel=1):
        """
        获取 MJPEG 子码流 URL（前端可直接用 <img> 标签显示）
        需要浏览器支持 Digest 认证（通常不支持），所以需要后端代理
        """
        return self._isapi(f'/ISAPI/Streaming/channels/{channel}01/httppreview')

    def mjpeg_stream_generator(self, channel=1):
        """
        生成器：持续从摄像头拉取 MJPEG 帧，yield (frame_bytes, boundary)
        用于后端代理流，配合 multipart/x-mixed-replace 响应
        """
        url = self.get_mjpeg_url(channel)
        try:
            resp = self._session.get(url, stream=True, timeout=(5, 0))
            if resp.status_code != 200:
                yield None, f"无法连接摄像头: HTTP {resp.status_code}"
                return

            boundary = None
            content_type = resp.headers.get('Content-Type', '')
            if 'boundary=' in content_type:
                boundary = content_type.split('boundary=')[-1].strip()

            buffer = b''
            for chunk in resp.iter_content(chunk_size=4096):
                if not chunk:
                    break
                buffer += chunk

                # 按 boundary 切分帧
                if boundary:
                    boundary_bytes = f'--{boundary}'.encode()
                    while boundary_bytes in buffer:
                        idx = buffer.find(boundary_bytes)
                        if idx == -1:
                            break
                        # 找到下一帧的起始
                        next_idx = buffer.find(boundary_bytes, idx + len(boundary_bytes))
                        if next_idx == -1:
                            break
                        frame_data = buffer[idx:next_idx]
                        buffer = buffer[next_idx:]
                        # 提取 JPEG 数据
                        header_end = frame_data.find(b'\r\n\r\n')
                        if header_end != -1:
                            jpeg_data = frame_data[header_end + 4:]
                            if jpeg_data.strip():
                                yield jpeg_data, boundary
                else:
                    # 无 boundary，直接 yield 每段数据
                    if buffer:
                        yield buffer, None
                        buffer = b''

        except requests.RequestException as e:
            yield None, str(e)

    # ==================== 云台控制 ====================

    def _ptz_control(self, pan=0, tilt=0, zoom=0, duration_ms=500):
        """
        云台连续运动控制
        pan: 水平 -100~100 (负=左，正=右)
        tilt: 垂直 -100~100 (负=下，正=上)
        zoom: 变焦 -100~100 (负=缩小，正=放大)
        duration_ms: 运动持续时间(毫秒)，之后自动停止
        """
        xml_body = (
            '<PTZData>'
            f'<pan>{pan}</pan>'
            f'<tilt>{tilt}</tilt>'
            f'<zoom>{zoom}</zoom>'
            '</PTZData>'
        )
        headers = {'Content-Type': 'application/xml'}

        try:
            # 发送移动指令
            resp = self._session.put(
                self._isapi('/ISAPI/PTZCtrl/channels/1/continuous'),
                data=xml_body, headers=headers, timeout=self.timeout
            )
            if resp.status_code not in (200, 202):
                return False, f"PTZ 控制失败: HTTP {resp.status_code}"

            # 等待指定时间后发送停止指令
            if duration_ms > 0:
                time.sleep(duration_ms / 1000.0)
                stop_xml = '<PTZData><pan>0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>'
                self._session.put(
                    self._isapi('/ISAPI/PTZCtrl/channels/1/continuous'),
                    data=stop_xml, headers=headers, timeout=self.timeout
                )

            return True, 'ok'
        except requests.RequestException as e:
            return False, str(e)

    def ptz_up(self, speed=5, duration_ms=500):
        return self._ptz_control(tilt=speed, duration_ms=duration_ms)

    def ptz_down(self, speed=5, duration_ms=500):
        return self._ptz_control(tilt=-speed, duration_ms=duration_ms)

    def ptz_left(self, speed=5, duration_ms=500):
        return self._ptz_control(pan=-speed, duration_ms=duration_ms)

    def ptz_right(self, speed=5, duration_ms=500):
        return self._ptz_control(pan=speed, duration_ms=duration_ms)

    def ptz_zoom_in(self, speed=5, duration_ms=500):
        return self._ptz_control(zoom=speed, duration_ms=duration_ms)

    def ptz_zoom_out(self, speed=5, duration_ms=500):
        return self._ptz_control(zoom=-speed, duration_ms=duration_ms)

    def ptz_action(self, action, speed=5, duration_ms=500):
        """统一的云台控制接口"""
        actions = {
            'up': self.ptz_up,
            'down': self.ptz_down,
            'left': self.ptz_left,
            'right': self.ptz_right,
            'zoomIn': self.ptz_zoom_in,
            'zoomOut': self.ptz_zoom_out,
        }
        fn = actions.get(action)
        if fn:
            return fn(speed=speed, duration_ms=duration_ms)
        return False, f'不支持的动作: {action}'

    # ==================== 分辨率 ====================

    def get_capabilities(self):
        """获取通道能力集（含支持的分辨率列表）"""
        try:
            resp = self._session.get(
                self._isapi('/ISAPI/Streaming/channels/1/capabilities'),
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.text, None
            return None, f"获取能力集失败: HTTP {resp.status_code}"
        except requests.RequestException as e:
            return None, str(e)

    def get_resolutions(self):
        """
        解析并返回可用分辨率列表
        返回: [(width, height, label), ...]
        """
        xml_text, error = self.get_capabilities()
        if error:
            return [], error

        # 简单解析 XML 中的分辨率
        import re
        resolutions = []
        seen = set()
        # 匹配 <resolutionWidth>1920</resolutionWidth><resolutionHeight>1080</resolutionHeight>
        pattern = r'<resolutionWidth>(\d+)</resolutionWidth>\s*<resolutionHeight>(\d+)</resolutionHeight>'
        matches = re.findall(pattern, xml_text)
        for w, h in matches:
            key = (int(w), int(h))
            if key not in seen:
                seen.add(key)
                resolutions.append({'width': key[0], 'height': key[1], 'label': f'{w}×{h}'})

        if not resolutions:
            # 回退：尝试常见分辨率
            resolutions = [
                {'width': 1920, 'height': 1080, 'label': '1920×1080'},
                {'width': 1280, 'height': 720, 'label': '1280×720'},
                {'width': 704, 'height': 576, 'label': '704×576'},
            ]
        return resolutions, None

    def set_resolution(self, width, height):
        """设置主码流分辨率"""
        xml_body = (
            '<StreamingChannel>'
            '<id>1</id>'
            '<Video>'
            '<resolutionWidth>' + str(width) + '</resolutionWidth>'
            '<resolutionHeight>' + str(height) + '</resolutionHeight>'
            '</Video>'
            '</StreamingChannel>'
        )
        headers = {'Content-Type': 'application/xml'}
        try:
            resp = self._session.put(
                self._isapi('/ISAPI/Streaming/channels/1'),
                data=xml_body, headers=headers, timeout=self.timeout
            )
            return resp.status_code in (200, 202), resp.text
        except requests.RequestException as e:
            return False, str(e)


# ==================== 摄像头连接池 ====================

_camera_pool = {}
_pool_lock = threading.Lock()


def get_camera(base_url, username, password, timeout=10):
    """获取或创建摄像头实例（按 base_url 缓存）"""
    key = f"{base_url}:{username}"
    with _pool_lock:
        if key not in _camera_pool:
            cam = HikvisionCamera(base_url, username, password, timeout)
            _camera_pool[key] = cam
        return _camera_pool[key]


def remove_camera(base_url, username):
    """从连接池移除摄像头实例"""
    key = f"{base_url}:{username}"
    with _pool_lock:
        _camera_pool.pop(key, None)


def get_project_camera(project):
    """从 AnnotationProject 对象获取摄像头实例"""
    if not project.camera_url:
        return None, '项目未配置摄像头'
    if not project.camera_username:
        return None, '摄像头用户名未配置'
    if not project.camera_password:
        return None, '摄像头密码未配置'

    cam = get_camera(project.camera_url, project.camera_username, project.camera_password)
    return cam, None
