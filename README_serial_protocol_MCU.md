# 串口协议使用说明书-MCU（Created by EtherealTide）

## 1. 协议格式

**协议格式：** 帧头(1字节) + 数据长度(1字节) + 数据(n字节) + 校验位(1字节) + 帧尾(1字节)

**协议常量：**
- 帧头：`0xAA`
- 帧尾：`0xBB`
- 最大数据长度：255字节


## 2. 用户接口
### 2.1 依赖环境与配置选项
- STM32 HAL 库（已初始化 UART，MX中串口要配置全局中断）
- `serial_protocol.h` 和 `serial_protocol.c` 文件已加入工程
- 注意serial_protocol.h中导入的.h文件要随单片机型号改变而调整（如果使用STM32F103C8T6还需要把函数中所有的UART替换为USART，例如UART_HandleTypeDef *huart->USART_HandleTypeDef *huart）
- `RX_BUFFER_SIZE`: 接收缓冲区大小（默认512字节）
- `MAX_DATA_LENGTH`: 最大数据长度（默认255字节）
---

### 2.2 协议控制

#### 2.2.1 初始化

```c
void SerialProtocol_Init(SerialProtocol_t *protocol, UART_HandleTypeDef *huart)
```

- **Args：**
  - `protocol`：协议实例指针
  - `huart`：使用的串口名指针，如&huart1

- **说明：**
  - 初始化设定串口通信口
  - 通常在程序最开始调用一次

#### 2.2.2 启动接收

```c
void SerialProtocol_StartReceive(SerialProtocol_t *protocol)
```

- **Args：**
  - `protocol`：协议实例指针

- **说明：**
  - 启动中断接收模式
  - 通常在初始化后调用一次

#### 2.2.3 停止接收

```c
void SerialProtocol_StopReceive(SerialProtocol_t *protocol)
```

- **Args：**

  - `protocol`：协议实例指针

- **说明：**

  - 停止中断接收模式

  - 用于暂停数据接收或系统关闭时调用

    

### 2.3 发送数据

```c
int SerialProtocol_Send(SerialProtocol_t *protocol, const uint8_t *data, uint8_t data_len, uint32_t timeout)
```

- **Args：**
  - `protocol`：协议实例指针（通过`SerialProtocol_Init`初始化）
  - `data`：要发送的数据数组首地址
  - `data_len`：要发送的数据长度（最大255）
  - `timeout`：发送超时时间（ms）

- **返回值：**
  - 0：发送成功
  - -1：发送失败（如数据超长、硬件异常等）

- **示例：**
  ```c
  uint8_t tx_data[3] = {0x11, 0x22, 0x33};
  SerialProtocol_Send(&protocol, tx_data, 3, 100);
  ```

---

### 2.4 数据接收与处理

#### 2.4.1 处理接收缓冲区
```c
int SerialProtocol_Process(SerialProtocol_t *protocol)
```

- **Args：**
  - `protocol`：协议实例指针

- **返回值：**
  - 0：成功接收到完整数据帧
  - 1：暂无完整数据帧（继续等待）

#### 2.4.2 解包正确格式的数据，并准备接收下一帧
```c
int SerialProtocol_GetReceivedFrame(SerialProtocol_t *protocol, uint8_t *data, uint8_t *data_len)
```

- **Args：**
  - `protocol`：协议实例指针
  - `data`：用于存放接收到的数据的数组首地址
  - `data_len`：用于存放接收数据长度的指针

- **返回值：**
  - 0：成功获取数据
  - -1：无可用数据

#### 2.4.3 中断回调函数
```c
void SerialProtocol_RxCallback(SerialProtocol_t *protocol)
```

- **Args：**
  - `protocol`：协议实例指针

- **说明：**
  - 在`HAL_UART_RxCpltCallback`中调用此函数
  - 用于处理每个接收到的字节
---



## 3. 完整调用实例

```C
#include "serial_protocol.h"

//1. 初始化
SerialProtocol_t protocol;
SerialProtocol_Init(&protocol, &huart1); //假设使用的是huart1
SerialProtocol_StartReceive(&protocol); // 开启中断接收模式
// 处理接收到的数据
void handle_received_data(uint8_t *data, uint8_t len) {
    // 根据您的应用需求处理接收到的数据
    // 例如：
    switch (data[0]) {
        case 0x01: // 命令1
            // 处理命令1
            break;
        case 0x02: // 命令2
            // 处理命令2
            break;
        default:
            // 未知命令
            break;
    }
}
//2. 中断回调设置
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart == &huart1) {
        SerialProtocol_RxCallback(&protocol);
    }
}


//3. 主循环处理

while (1) {
        // 处理接收缓冲区
        if (SerialProtocol_Process(&protocol) == 0) {
            // 解包数据，并准备接收下一帧
            if (SerialProtocol_GetReceivedFrame(&protocol, received_data, &data_len) == 0) {
                // 成功接收到数据，进行处理
                handle_received_data(received_data, data_len);
            }
        }
        
        // 其他主循环任务
        other_tasks();
        
        // 可以添加适当的延时
        HAL_Delay(1);
    }

//4.发送数据部分示例
uint8_t data[] = {0x01, 0x02, 0x03};
SerialProtocol_Send(&protocol, data, sizeof(data), 1000);

```
## 4. 发送流程详解

```
用户调用 SerialProtocol_Send(&protocol, data, data_len, timeout)
                    ↓
            检查数据长度是否合法
            if (data_len > MAX_DATA_LENGTH) return -1
                    ↓
            调用 calculate_checksum() 计算校验和
                    ↓
┌─────────────────────────────────────────────────────┐
│                数据打包流程                          │
│                                                     │
│  1. 检查数据长度                                     │
│     data_len <= MAX_DATA_LENGTH (255)               │
│                    ↓                                │
│  2. 创建发送缓冲区                                   │
│     uint8_t frame[4 + MAX_DATA_LENGTH]              │
│     frame_len = 4 + data_len                        │
│                    ↓                                │
│  3. 组装帧结构                                       │
│     frame[0] = FRAME_HEAD (0xAA)                    │
│     frame[1] = data_len                             │
│     for (i=0; i<data_len; i++) frame[2+i] = data[i]│
│                    ↓                                │
│  4. 计算校验和                                       │
│     checksum = calculate_checksum(&frame[1], 1+data_len) │
│     frame[2 + data_len] = checksum                  │
│                    ↓                                │
│  5. 添加帧尾                                         │
│     frame[3 + data_len] = FRAME_TAIL (0xBB)         │
│     完整帧: AA data_len [data...] checksum BB        │
└─────────────────────────────────────────────────────┘
                    ↓
            调用 HAL_UART_Transmit() 发送
            HAL_UART_Transmit(huart, frame, frame_len, timeout)
                    ↓
            检查发送结果
            if (result == HAL_OK) return 0
            else return -1
```

## 5. 接收流程详解

```
UART硬件接收到字节数据
        ↓
触发 HAL_UART_RxCpltCallback() 中断
        ↓
调用 SerialProtocol_RxCallback(&protocol)
        ↓
┌─────────────────────────────────────────────────────────────┐
│                中断接收处理流程                              │
│                                                             │
│  1. 字节数据写入环形缓冲区                                   │
│     buffer_write(protocol, protocol->rx_byte)                │
│     protocol->rx_buffer[head] = rx_byte                      │
│     head = (head + 1) % RX_BUFFER_SIZE                      │
│                    ↓                                        │
│  2. 处理缓冲区满的情况                                       │
│     if (head == tail) // 缓冲区满                           │
│         tail = (tail + 1) % RX_BUFFER_SIZE // 丢弃最旧数据   │
│                    ↓                                        │
│  3. 重新启动接收中断                                         │
│     HAL_UART_Receive_IT(huart, &rx_byte, 1)                │
│     等待下一个字节                                           │
└─────────────────────────────────────────────────────────────┘
        ↓
主循环调用 SerialProtocol_Process(&protocol)
        ↓
┌─────────────────────────────────────────────────────────────┐
│                状态机解析流程                                │
│                                                             │
│  1. 从环形缓冲区读取字节                                     │
│     while (buffer_available(protocol))                      │
│         buffer_read(protocol, &byte)                        │
│                    ↓                                        │
│  2. 状态机处理                                               │
│     switch (protocol->rx_state)                             │
│                    ↓                                        │
│  3. RX_STATE_IDLE: 等待帧头                                 │
│     if (byte == FRAME_HEAD) // 0xAA                         │
│         rx_state = RX_STATE_HEAD_FOUND                      │
│                    ↓                                        │
│  4. RX_STATE_HEAD_FOUND: 获取数据长度                       │
│     if (byte <= MAX_DATA_LENGTH)                            │
│         expected_length = byte                              │
│         rx_state = RX_STATE_LENGTH_RECEIVED                 │
│                    ↓                                        │
│  5. RX_STATE_LENGTH_RECEIVED: 接收数据                      │
│     frame_data[received_length++] = byte                    │
│     if (received_length >= expected_length)                 │
│         rx_state = RX_STATE_DATA_RECEIVING                  │
│                    ↓                                        │
│  6. RX_STATE_DATA_RECEIVING: 校验和验证                     │
│     expected_checksum = calculate_checksum(...)             │
│     if (byte == expected_checksum)                          │
│         准备接收帧尾                                          │
│     else 重新开始 (rx_state = RX_STATE_IDLE)                │
│                    ↓                                        │
│  7. 接收帧尾                                                 │
│     if (byte == FRAME_TAIL) // 0xBB                         │
│         frame_ready = 1                                     │
│         rx_state = RX_STATE_FRAME_COMPLETE                  │
│         return 0 // 成功接收完整帧                           │
└─────────────────────────────────────────────────────────────┘
        ↓
主循环检测到完整帧 (返回值 == 0)
        ↓
调用 SerialProtocol_GetReceivedFrame(&protocol, data, &data_len)
        ↓
┌─────────────────────────────────────────────────────┐
│                数据解包流程                           │
│                                                     │
│  1. 检查帧是否就绪                                    │
│     if (!protocol->frame_ready) return -1           │
│                    ↓                                │
│  2. 拷贝数据到用户缓冲区                              │
│     for (i=0; i<frame_length; i++)                  │
│         data[i] = protocol->frame_data[i]            │
│     *data_len = protocol->frame_length               │
│                    ↓                                │
│  3. 清除帧标志，准备接收下一帧                        │
│     protocol->frame_ready = 0                       │
│     protocol->rx_state = RX_STATE_IDLE               │
│                    ↓                                │
│  4. 返回成功                                          │
│     return 0                                        │
└─────────────────────────────────────────────────────┘
        ↓
用户获取解包后的数据
handle_received_data(data, data_len)
```

## 6. 错误处理机制

### 6.1 发送错误处理
- **数据长度超限**：`if (data_len > MAX_DATA_LENGTH) return -1`
- **UART发送失败**：`if (HAL_UART_Transmit() != HAL_OK) return -1`
- **硬件故障**：返回错误码，上层应用处理

### 6.2 接收错误处理
- **帧头不匹配**：`rx_state = RX_STATE_IDLE`，重新开始寻找帧头
- **数据长度无效**：`rx_state = RX_STATE_IDLE`，丢弃当前帧
- **校验失败**：`rx_state = RX_STATE_IDLE`，丢弃损坏数据
- **帧尾错误**：`rx_state = RX_STATE_IDLE`，重新开始解析
- **缓冲区溢出**：自动丢弃最旧数据，保持接收

## 7. 数据流完整示例

```
发送端:
用户数据: {0x01, 0x02, 0x03}
    ↓
SerialProtocol_Send(&protocol, data, 3, 1000)
    ↓
打包后: AA 03 01 02 03 09 BB
    ↓
HAL_UART_Transmit(): 7字节数据通过UART发送
    ↓
    
接收端:
UART中断接收: AA 03 01 02 03 09 BB (逐字节)
    ↓
SerialProtocol_RxCallback(): 每个字节存入环形缓冲区
    ↓
SerialProtocol_Process(): 状态机解析完整帧
    ↓
SerialProtocol_GetReceivedFrame(): 提取数据给用户
    ↓
用户获取: {0x01, 0x02, 0x03}
```

## 8. 协议优势

1. **非阻塞性**：中断驱动，主循环不会被串口接收阻塞
2. **实时性**：硬件中断保证数据及时处理
3. **健壮性**：状态机解析，自动错误恢复
4. **高效性**：环形缓冲区，防止数据丢失
5. **易用性**：简洁的API接口，易于集成到现有项目