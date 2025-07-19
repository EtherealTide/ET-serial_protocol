# 串口协议使用说明书-Python（Created by EtherealTide）

## 1. 协议格式

**协议格式：** 帧头(1字节) + 数据长度(1字节) + 数据(n字节) + 校验位(1字节) + 帧尾(1字节)

**协议常量：**
- 帧头：`0xAA`
- 帧尾：`0xBB`
- 最大数据长度：255字节

## 2. 用户接口

### 2.1 初始化和连接
```python
# 创建串口协议实例
serial_protocol = SerialProtocol(port="COM1", baudrate=115200, timeout=1.0)

# 连接串口
if serial_protocol.connect():
    print("串口连接成功")
else:
    print("串口连接失败")
```

### 2.2 发送数据接口
```python
# 发送数据数组
data_to_send = [0x01, 0x02, 0x03, 0x04, 0x05]
success = serial_protocol.send_data(data_to_send)
```

### 2.3 接收数据接口

**方式1：主线程的阻塞接收**
```python
# 阻塞接收数据，设置超时时间
received_data = serial_protocol.receive_data(timeout=5.0)
if received_data:
    print(f"接收到数据: {received_data}")
else:
    print("接收超时")
```

**方式2：分线程的非阻塞接收**
```python
# 设置回调函数方式（注意并非中断回调，只是在分线程中处理接收数据）
def on_data_received(data):
    print(f"回调接收到数据: {data}")

def on_error(error):
    print(f"错误: {error}")

serial_protocol.set_data_received_callback(on_data_received)
serial_protocol.set_error_callback(on_error)
```

### 2.4 其他接口
```python
# 清空接收缓冲区
serial_protocol.clear_receive_buffer()

# 获取串口状态
status = serial_protocol.get_status()
print(f"串口状态: {status}")

# 断开连接
serial_protocol.disconnect()
```

## 3. 完整调用实例
```python
import serial_protocol

def main():
    # 定义回调函数
    def on_data_received(data):
        print(f"接收到数据: {data}")
        # 处理接收到的数据
        if data[0] == 0x01:  # 命令帧
            handle_command(data[1:])
        elif data[0] == 0x02:  # 数据帧
            handle_sensor_data(data[1:])
    
    def on_error(error):
        print(f"串口错误: {error}")
    
    # 创建串口协议实例
    protocol = SerialProtocol("COM1", 115200)
    
    # 设置回调函数
    protocol.set_data_received_callback(on_data_received)
    protocol.set_error_callback(on_error)
    
    # 连接串口
    if protocol.connect():
        try:
            # 发送数据
            protocol.send_data([0x01, 0x10, 0x20])  
            protocol.send_data([0x02, 0x11, 0x22, 0x33])
            
            # 等待接收数据
            while True:
                data = protocol.receive_data(timeout=1.0)
                if data:
                    print(f"主线程接收到: {data}")
                else:
                    print("等待数据...")
                    
        except KeyboardInterrupt:
            print("程序中断")
        finally:
            protocol.disconnect()
    else:
        print("串口连接失败")

if __name__ == "__main__":
    main()
```

## 4. 发送流程详解

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
            通过串口发送字节数据
            self.serial_conn.write(frame)
                    ↓
            发送完成，返回成功状态
```

## 5. 接收流程详解

```
while循环
串口每接收到一次字节数据
        ↓
接收线程将数据写入缓冲区
receive_buffer += new_data
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
│     尝试读取数据长度: data_length = 0x05                       │
│     计算应有帧长度: frame_length = 1+1+5+1+1 = 9               │
│     尝试检查是否存在这个长度的帧                                 │
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
数据分发到两个目标
        ↓
┌─────────────────┐     ┌─────────────────┐
│   放入接收队列    │     │   调用回调函数    │
│                  │     │                │
│ receive_queue   │     │ on_data_received │
│   .put(data)    │     │    (data)       │
│                │     │                │
│   用于主线程阻塞接收│  │  用于直接在分线程实时处理│
└─────────────────┘     └─────────────────┘
```

## 6. 错误处理机制

### 6.1 发送错误处理
- **串口未连接**：返回False，输出错误信息
- **数据长度超限**：抛出ValueError异常
- **串口写入异常**：捕获异常，调用错误回调

### 6.2 接收错误处理
- **帧头不匹配**：丢弃无效数据，继续查找下一个帧头
- **帧长度不匹配**：丢弃该帧，继续处理缓冲区
- **校验失败**：丢弃损坏数据，不放入接收队列
- **线程异常**：停止接收线程，调用错误回调

## 7. 数据流完整示例

```
发送端:
用户数据: [1, 2, 3, 4, 5]
    ↓
打包后: AA 05 01 02 03 04 05 14 BB
    ↓
串口发送: 9字节数据
    ↓
    
接收端:
串口接收: AA 05 01 02 03 04 05 14 BB
    ↓
缓冲区处理: 查找帧头、提取帧数据
    ↓
数据解包: 校验通过、提取数据
    ↓
数据分发: 队列 + 回调
    ↓
用户获取: [1, 2, 3, 4, 5]
```

## 8. 协议优势

1. **可靠性**：帧头帧尾确保帧边界，校验和确保数据完整性
2. **实时性**：后台接收线程确保数据实时处理
3. **灵活性**：支持阻塞接收和回调接收两种模式
4. **健壮性**：完善的错误处理和数据恢复机制
5. **易用性**：简洁的API接口，支持多种使用场景
