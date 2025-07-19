# 串口协议使用说明书-MaixCAM版本（Created by EtherealTide）

## 1. 协议格式

**协议格式：** 帧头(1字节) + 数据长度(1字节) + 数据(n字节) + 校验位(1字节) + 帧尾(1字节)

**协议常量：**
- 帧头：`0xAA`
- 帧尾：`0xBB`
- 最大数据长度：255字节

## 2. MaixCAM版本特性

| 特性     | 标准Python版本    | MaixCAM版本      |
| -------- | ----------------- | ---------------- |
| 串口库   | `pyserial`        | `maix.uart`      |
| 接收模式 | 专用接收线程      | uart库定义的中断回调    |
| 连接方式 | `serial.Serial()` | `uart.UART()`    |
| 数据处理 | 线程池处理        | 中断直接处理     |


## 3. 用户接口

### 3.1 初始化和连接
```python
from serial_protocol import SerialProtocol
from maix import uart

# 创建串口协议实例
protocol = SerialProtocol("/dev/ttyS0", 115200)

# 连接串口
protocol.connect():
```

### 3.2 发送数据接口
```python
# 发送数据数组
data_to_send = [0x01, 0x02, 0x03, 0x04, 0x05]
success = protocol.send_data(data_to_send)
if success:
    print("数据发送成功")
else:
    print("数据发送失败")
```

### 3.3 接收数据接口 - 中断回调

**设置解包后的回调函数（与标准python版本一致）**
```python
def on_data_received(data):
    """数据接收回调函数"""
    print(f"接收到数据: {data}")
    # 处理接收到的数据
    if data[0] == 0x01:  # 命令帧
        handle_command(data[1:])
    elif data[0] == 0x02:  # 数据帧
        handle_sensor_data(data[1:])

def on_error(error):
    """错误回调函数"""
    print(f"协议错误: {error}")

# 设置回调函数
protocol.set_data_received_callback(on_data_received)
protocol.set_error_callback(on_error)
```

**使用uart库的串口中断回调作为处理数据的启动器（注意两个回调的区别）**
```python
def on_received(serial: uart.UART, data: bytes):
    """串口接收中断回调函数"""
    try:
        # 将接收到的原始数据传递给协议处理器
        protocol.process_received_data(data)
    except Exception as e:
        print(f"[ERROR] 回调异常: {e}")

# 设置串口接收回调
protocol.serial_conn.set_received_callback(on_received)
```

### 3.4 其他接口
```python
# 断开连接
protocol.disconnect()

# 检查连接状态
if protocol.is_connected:
    print("串口已连接")
```

## 4. 完整调用实例

```python
from maix import uart
from serial_protocol import SerialProtocol

def main():
    # 定义数据接收回调函数
    def on_data_received(data):
        print(f"接收到数据: {data}")
        # 处理不同类型的数据
        if len(data) > 0:
            cmd = data[0]
            if cmd == 0x01:  # 参数设置命令
                handle_parameter_setting(data[1:])
            elif cmd == 0x02:  # 状态查询命令
                handle_status_query(data[1:])
            elif cmd == 0x03:  # 数据传输命令
                handle_data_transfer(data[1:])
    
    def on_error(error):
        print(f"串口错误: {error}")
    
    # 串口中断回调函数
    def on_received(serial: uart.UART, data: bytes):
        try:
            protocol.process_received_data(data)
        except Exception as e:
            print(f"[ERROR] 中断回调异常: {e}")
    
    # 创建串口协议实例
    protocol = SerialProtocol("/dev/ttyS0", 115200)
    
    # 设置回调函数
    protocol.set_data_received_callback(on_data_received)
    protocol.set_error_callback(on_error)
    
    # 连接串口
    if protocol.connect():
        try:
            # 设置串口中断回调
            protocol.serial_conn.set_received_callback(on_received)
            
            # 发送初始化数据
            protocol.send_data([0x01, 0x00])  # 初始化命令
            protocol.send_data([0x02, 0x01])  # 状态查询
            
            # 主循环（MaixCAM通常在主循环中处理其他任务）
            while True:
                # 处理其他任务（如摄像头、显示等）
                # 串口数据接收由中断自动处理
                pass
                
        except KeyboardInterrupt:
            print("程序中断")
        finally:
            protocol.disconnect()
    else:
        print("串口连接失败")

def handle_parameter_setting(data):
    """处理参数设置命令"""
    print(f"参数设置: {data}")

def handle_status_query(data):
    """处理状态查询命令"""
    print(f"状态查询: {data}")

def handle_data_transfer(data):
    """处理数据传输命令"""
    print(f"数据传输: {data}")

if __name__ == "__main__":
    main()
```

## 5. 发送流程详解

```
用户调用 send_data([0x01, 0x02, 0x03, 0x04, 0x05])
                    ↓
            检查串口连接状态
                    ↓
            调用 pack_frame() 打包数据
                    ↓
┌─────────────────────────────────────────────────────┐
│                数据打包流程                          │
│                                                     │
│  1. 检查数据长度                                     │
│     len(data) <= 255                                │
│                    ↓                                │
│  2. 准备数据                                         │
│     data_length = 5                                 │
│     data_bytes = b'\x01\x02\x03\x04\x05'            │
│                    ↓                                │
│  3. 构建校验数据                                     │
│     checksum_data = b'\x05\x01\x02\x03\x04\x05'     │
│                    ↓                                │
│  4. 计算校验和                                       │
│     checksum = (0x05+0x01+0x02+0x03+0x04+0x05)&0xFF │
│     checksum = 0x14                                 │
│                    ↓                                │
│  5. 组装完整帧                                       │
│     frame = 0xAA + 0x05 + data + 0x14 + 0xBB        │
│     frame = AA 05 01 02 03 04 05 14 BB              │
└─────────────────────────────────────────────────────┘
                    ↓
            通过MaixCAM UART发送
            self.serial_conn.write(frame)
                    ↓
            发送完成，返回成功状态
```

## 6. 接收流程详解

```
硬件串口接收到数据
        ↓
触发MaixCAM UART中断
        ↓
调用 on_received() 中断回调函数
        ↓
调用 protocol.process_received_data(data)
        ↓
将新数据添加到接收缓冲区
receive_buffer += data
        ↓
调用 _process_receive_buffer() 处理缓冲区
        ↓
┌─────────────────────────────────────────────────────────────┐
│                缓冲区处理流程                                 │
│                                                             │
│  1. 查找帧头                                                 │
│     在缓冲区中查找 0xAA                                        │
│     假设: b'\x12\x34\xAA\x05\x01\x02\x03\x04\x05\x14\xBB\x67'│
│                    ↓                                        │
│  2. 删除无效数据                                              │
│     删除帧头前的数据: b'\x12\x34'                              │
│     缓冲区变为: b'\xAA\x05\x01\x02\x03\x04\x05\x14\xBB\x67'   │
│                    ↓                                        │
│  3. 检查数据完整性                                             │
│     读取数据长度: data_length = 0x05                          │
│     计算应有帧长度: frame_length = 1+1+5+1+1 = 9               │
│     检查是否有足够数据                                          │
│                    ↓                                        │
│  4. 提取完整帧                                                │
│     frame_data = b'\xAA\x05\x01\x02\x03\x04\x05\x14\xBB'    │
│     剩余缓冲区: b'\x67'                                       │
└─────────────────────────────────────────────────────────────┘
        ↓
调用 unpack_frame() 解包数据
        ↓
┌─────────────────────────────────────────────────────┐
│                数据解包流程                           │
│                                                     │
│  1. 基本验证                                          │
│     检查帧长度 >= 4                                   │
│     检查帧头 == 0xAA                                 │
│     检查帧尾 == 0xBB                                 │
│                    ↓                                │
│  2. 数据提取                                          │
│     data_length = frame_data[1] = 0x05              │
│     data_bytes = frame_data[2:7] = b'\x01\x02\x03\x04\x05' │
│     received_checksum = frame_data[7] = 0x14        │
│                    ↓                                │
│  3. 校验验证                                          │
│     重新计算校验和                                     │
│     calculated_checksum = (0x05+0x01+0x02+0x03+0x04+0x05) & 0xFF │
│     calculated_checksum = 0x14                      │
│     比较: received_checksum == calculated_checksum   │
│                    ↓                                │
│  4. 数据转换                                          │
│     data_array = [1, 2, 3, 4, 5]                   │
│     返回解包后的数据                                   │
└─────────────────────────────────────────────────────┘
        ↓
    ┌─────────────────┐
    │   调用回调函数   │
    │                 │
    │ on_data_received│
    │    (data)       │
    │                 │
    │   处理解包数据   │
    └─────────────────┘
```



## 7. 协议优势总结

1. **硬件优化**：利用MaixCAM硬件中断，响应速度快
2. **资源节约**：无需独立接收线程，节省系统资源
3. **实时性强**：中断驱动确保数据实时处理
4. **可靠性高**：完善的帧格式和校验机制
5. **易于集成**：与MaixCAM生态系统完美集成

## 8. 数据流完整示例

```
发送端:
用户数据: [1, 2, 3, 4, 5]
    ↓
打包后: AA 05 01 02 03 04 05 14 BB
    ↓
MaixCAM UART发送: 9字节数据
    ↓
    
接收端:
MaixCAM UART接收: AA 05 01 02 03 04 05 14 BB
    ↓
硬件中断触发: on_received()
    ↓
缓冲区处理: 查找帧头、提取帧数据
    ↓
数据解包: 校验通过、提取数据
    ↓
数据分发: 队列 + 回调
    ↓
用户获取: [1, 2, 3, 4, 5]
```

