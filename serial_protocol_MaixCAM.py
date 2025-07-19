# Created by EtherealTide on 2025/7/15.
from typing import List, Optional, Callable
import struct
from maix import uart


class SerialProtocol:
    """
    串口通信协议类
    协议格式：帧头(1字节) + 数据长度(1字节) + 数据(n字节) + 校验位(1字节) + 帧尾(1字节)
    """

    # 协议常量
    FRAME_HEAD = 0xAA  # 帧头
    FRAME_TAIL = 0xBB  # 帧尾
    MAX_DATA_LENGTH = 255  # 最大数据长度

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        """
        初始化串口协议

        Args:
            port: 串口名称 (如 '/dev/ttyS0')
            baudrate: 波特率
            timeout: 超时时间
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_connected = False
        self.running = False

        # 回调函数
        self.on_data_received = None
        self.on_error = None

        # 接收缓冲区
        self.receive_buffer = b""
        self.max_buffer_size = 4096

    def connect(self) -> bool:
        """
        连接串口

        Returns:
            bool: 连接是否成功
        """
        try:
            self.serial_conn = uart.UART(self.port, self.baudrate)
            self.is_connected = True
            self.running = True

            print(f"串口 {self.port} 连接成功")
            return True

        except Exception as e:
            print(f"串口连接失败: {e}")
            if self.on_error:
                self.on_error(f"连接失败: {e}")
            return False

    def disconnect(self):
        """
        断开串口连接
        """
        self.running = False
        self.is_connected = False

        if self.serial_conn:
            try:
                self.serial_conn.close()
                print(f"串口 {self.port} 已断开")
            except:
                pass

    def _calculate_checksum(self, data: bytes) -> int:
        """
        计算校验和

        Args:
            data: 需要校验的数据

        Returns:
            int: 校验和 (0-255)
        """
        return sum(data) & 0xFF

    def pack_frame(self, data: List[int]) -> bytes:
        """
        打包数据帧

        Args:
            data: 要发送的数据数组

        Returns:
            bytes: 打包后的数据帧

        Raises:
            ValueError: 数据长度超过最大限制
        """
        if len(data) > self.MAX_DATA_LENGTH:
            raise ValueError(
                f"数据长度 {len(data)} 超过最大限制 {self.MAX_DATA_LENGTH}"
            )

        # 数据长度
        data_length = len(data)

        # 将数据转换为字节
        data_bytes = bytes(data)

        # 构建需要校验的部分：数据长度 + 数据
        checksum_data = struct.pack("B", data_length) + data_bytes

        # 计算校验和
        checksum = self._calculate_checksum(checksum_data)

        # 组装完整帧：帧头 + 数据长度 + 数据 + 校验位 + 帧尾
        frame = (
            struct.pack("B", self.FRAME_HEAD)
            + struct.pack("B", data_length)
            + data_bytes
            + struct.pack("B", checksum)
            + struct.pack("B", self.FRAME_TAIL)
        )

        return frame

    def unpack_frame(self, frame_data: bytes) -> Optional[List[int]]:
        """
        解包数据帧

        Args:
            frame_data: 接收到的数据帧

        Returns:
            Optional[List[int]]: 解包后的数据数组，如果解包失败返回None
        """
        # 检查帧长度
        if (
            len(frame_data) < 4
        ):  # 最小帧长度：1(帧头) + 1(长度) + 0(数据) + 1(校验) + 1(帧尾)
            return None

        # 检查帧头
        if frame_data[0] != self.FRAME_HEAD:
            return None

        # 检查帧尾
        if frame_data[-1] != self.FRAME_TAIL:
            return None

        # 获取数据长度
        data_length = frame_data[1]

        # 检查帧长度是否匹配
        expected_length = (
            1 + 1 + data_length + 1 + 1
        )  # 帧头 + 长度 + 数据 + 校验 + 帧尾
        if len(frame_data) != expected_length:
            return None

        # 提取数据
        data_bytes = frame_data[2 : 2 + data_length]

        # 提取校验位
        received_checksum = frame_data[2 + data_length]

        # 计算校验和
        checksum_data = struct.pack("B", data_length) + data_bytes
        calculated_checksum = self._calculate_checksum(checksum_data)

        # 校验
        if received_checksum != calculated_checksum:
            return None

        # 将字节数据转换为整数数组
        data_array = list(data_bytes)
        return data_array

    def send_data(self, data: List[int]) -> bool:
        """
        发送数据

        Args:
            data: 要发送的数据数组

        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected or not self.serial_conn:
            print("串口未连接")
            return False

        try:
            # 打包数据
            frame = self.pack_frame(data)

            # 发送字节数据
            self.serial_conn.write(frame)

            print(f"发送数据: {frame.hex()}")
            return True

        except Exception as e:
            print(f"发送数据失败: {e}")
            if self.on_error:
                self.on_error(f"发送失败: {e}")
            return False

    def process_received_data(self, data: bytes):
        """
        处理接收到的原始数据（在串口回调中调用）

        Args:
            data: 接收到的原始字节数据
        """
        try:
            # 添加到缓冲区
            self.receive_buffer += data

            # 防止缓冲区过大
            if len(self.receive_buffer) > self.max_buffer_size:
                self.receive_buffer = self.receive_buffer[-self.max_buffer_size // 2 :]
                print("[WARNING] 接收缓冲区过大，清理旧数据")

            # 处理接收缓冲区中的数据
            self._process_receive_buffer()

        except Exception as e:
            print(f"[ERROR] 处理接收数据异常: {e}")
            if self.on_error:
                self.on_error(f"处理接收数据异常: {e}")

    def _process_receive_buffer(self):
        """
        处理接收缓冲区中的数据
        """
        processed_count = 0
        max_process_per_call = 10  # 限制每次处理的帧数

        while len(self.receive_buffer) >= 4 and processed_count < max_process_per_call:
            # 查找帧头
            head_index = -1
            for i in range(len(self.receive_buffer)):
                if self.receive_buffer[i] == self.FRAME_HEAD:
                    head_index = i
                    break

            if head_index == -1:
                # 没有找到帧头，清空缓冲区
                self.receive_buffer = b""
                break

            # 删除帧头前的无效数据
            if head_index > 0:
                self.receive_buffer = self.receive_buffer[head_index:]

            # 检查是否有足够的数据来确定帧长度
            if len(self.receive_buffer) < 2:
                break

            # 获取数据长度
            data_length = self.receive_buffer[1]
            frame_length = (
                1 + 1 + data_length + 1 + 1
            )  # 帧头 + 长度 + 数据 + 校验 + 帧尾

            # 检查是否接收到完整帧
            if len(self.receive_buffer) < frame_length:
                break

            # 提取一帧数据
            frame_data = self.receive_buffer[:frame_length]
            self.receive_buffer = self.receive_buffer[frame_length:]

            # 解包数据
            unpacked_data = self.unpack_frame(frame_data)
            if unpacked_data is not None:
                try:
                    # 调用回调函数
                    if self.on_data_received:
                        try:
                            self.on_data_received(unpacked_data)
                        except Exception as e:
                            print(f"[ERROR] 回调函数异常: {e}")

                except Exception as e:
                    print(f"[ERROR] 处理解包数据异常: {e}")

    def set_data_received_callback(self, callback: Callable[[List[int]], None]):
        """
        设置数据接收回调函数

        Args:
            callback: 回调函数，参数为接收到的数据数组
        """
        self.on_data_received = callback

    def set_error_callback(self, callback: Callable[[str], None]):
        """
        设置错误回调函数

        Args:
            callback: 回调函数，参数为错误信息
        """
        self.on_error = callback
