# Created by EtherealTide on 2025/7/7.
import serial
import struct
import threading
import queue
import time
from typing import List, Optional, Callable


class SerialProtocol:
    """
    串口通信协议类
    协议格式：帧头(1字节) + 数据长度(1字节) + 数据(n字节) + 校验位(1字节) + 帧尾(1字节)
    """

    # 协议常量
    FRAME_HEAD = 0xAA  # 帧头
    FRAME_TAIL = 0xBB  # 帧尾
    MAX_DATA_LENGTH = 255  # 最大数据长度

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        """
        初始化串口协议

        Args:
            port: 串口名称 (如 'COM1', '/dev/ttyUSB0')
            baudrate: 波特率
            timeout: 超时时间
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_connected = False
        self.receive_thread = None
        self.receive_queue = queue.Queue()
        self.running = False

        # 回调函数
        self.on_data_received = None
        self.on_error = None

        # 接收缓冲区
        self.receive_buffer = b""

    def connect(self) -> bool:
        """
        连接串口

        Returns:
            bool: 连接是否成功
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self.is_connected = True
            self.running = True

            # 启动接收线程
            self.receive_thread = threading.Thread(
                target=self._receive_thread, daemon=True
            )
            self.receive_thread.start()

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

        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)

        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print(f"串口 {self.port} 已断开")

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
            self.serial_conn.flush()

            print(f"发送数据: {frame.hex()}")  # 调试输出显示十六进制
            return True

        except Exception as e:
            print(f"发送数据失败: {e}")
            if self.on_error:
                self.on_error(f"发送失败: {e}")
            return False

    def _receive_thread(self):
        """
        接收线程
        """
        while self.running and self.is_connected:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    # 读取数据 - 这里读取的就是字节数据
                    new_data = self.serial_conn.read(self.serial_conn.in_waiting)
                    self.receive_buffer += new_data

                    # 处理接收缓冲区中的数据
                    self._process_receive_buffer()

                time.sleep(0.001)  # 避免CPU占用过高

            except Exception as e:
                print(f"接收数据异常: {e}")
                if self.on_error:
                    self.on_error(f"接收异常: {e}")
                break

    def _process_receive_buffer(self):
        """
        处理接收缓冲区中的数据
        """
        while len(self.receive_buffer) >= 4:  # 最小帧长度
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
                # 将解包后的数据放入队列
                self.receive_queue.put(unpacked_data)

                # 调用回调函数
                if self.on_data_received:
                    self.on_data_received(unpacked_data)

    def receive_data(self, timeout: float = None) -> Optional[List[int]]:
        """
        接收数据（阻塞）

        Args:
            timeout: 超时时间，None表示无限等待

        Returns:
            Optional[List[int]]: 接收到的数据数组，超时返回None
        """
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None

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


# 使用示例和测试
if __name__ == "__main__":

    def on_data_received(data):
        print(f"接收到数据: {data}")

    def on_error(error):
        print(f"错误: {error}")

    # 创建串口协议实例
    serial_protocol = SerialProtocol("COM7", 115200)

    # 设置回调函数
    serial_protocol.set_data_received_callback(on_data_received)
    serial_protocol.set_error_callback(on_error)
    test_data = [0x01, 0x02, 0x03, 0x04, 0x05]
    # 1. 测试打包 - 得到字节数据
    frame = serial_protocol.pack_frame(test_data)
    print(f"打包后的帧 (bytes): {frame}")
    print(f"打包后的帧 (hex): {frame.hex()}")  # aa0501020304051455
    # 2. 模拟接收 - 直接将字节数据写入缓冲区
    print("\n--- 模拟接收处理 ---")
    serial_protocol.receive_buffer = frame  # 直接用字节数据
    print(f"接收缓冲区 (bytes): {serial_protocol.receive_buffer}")
    print(f"接收缓冲区 (hex): {serial_protocol.receive_buffer.hex()}")

    # 3. 处理接收缓冲区
    serial_protocol._process_receive_buffer()

    # 4. 测试阻塞接收
    received_data = serial_protocol.receive_data(timeout=0.1)
    print(f"阻塞接收到的数据: {received_data}")

    # 5. 测试多帧数据
    print("\n--- 测试多帧数据 ---")
    frame1 = serial_protocol.pack_frame([0x11, 0x22])
    frame2 = serial_protocol.pack_frame([0x33, 0x44, 0x55])

    # 模拟接收到连续的多帧字节数据
    multi_frame_data = frame1 + frame2
    serial_protocol.receive_buffer = multi_frame_data

    print(f"多帧数据 (hex): {multi_frame_data.hex()}")

    # 处理多帧数据
    serial_protocol._process_receive_buffer()

    # 接收多个帧
    data1 = serial_protocol.receive_data(timeout=0.1)
    data2 = serial_protocol.receive_data(timeout=0.1)
    print(f"第一个帧数据: {data1}")
    print(f"第二个帧数据: {data2}")

    # 6. 测试带噪声的数据
    print("\n--- 测试带噪声的数据 ---")
    noise_data = b"\x12\x34\x56" + frame + b"\x78\x90"
    serial_protocol.receive_buffer = noise_data

    print(f"带噪声数据 (hex): {noise_data.hex()}")

    # 处理带噪声的数据
    serial_protocol._process_receive_buffer()

    # 应该能正确提取出有效数据
    clean_data = serial_protocol.receive_data(timeout=0.1)
    print(f"从噪声中提取的数据: {clean_data}")
