// Created by EtherealTide on 2025/7/7.
#include "serial_protocol.h"
#include <string.h>

// 计算校验和
static uint8_t calculate_checksum(const uint8_t *data, uint8_t len)
{
    uint16_t sum = 0;
    for (uint8_t i = 0; i < len; ++i)
        sum += data[i];
    return (uint8_t)(sum & 0xFF);
}

// 初始化协议
void SerialProtocol_Init(SerialProtocol_t *protocol, UART_HandleTypeDef *huart)
{
    protocol->huart = huart;
    protocol->rx_head = 0;              // 环形缓冲区头指针
    protocol->rx_tail = 0;              // 环形缓冲区尾指针
    protocol->rx_state = RX_STATE_IDLE; // 接收状态
    protocol->expected_length = 0;      // 期望接收的数据长度
    protocol->received_length = 0;      // 已接收的数据长度
    protocol->frame_length = 0;         // 当前帧长度
    protocol->frame_ready = 0;          // 帧准备就绪标志
    memset(protocol->rx_buffer, 0, sizeof(protocol->rx_buffer));
    memset(protocol->frame_data, 0, sizeof(protocol->frame_data));
}

// 启动接收（启用中断）
void SerialProtocol_StartReceive(SerialProtocol_t *protocol)
{
    HAL_UART_Receive_IT(protocol->huart, &protocol->rx_byte, 1);
}

// 停止接收（禁用中断）
void SerialProtocol_StopReceive(SerialProtocol_t *protocol)
{
    HAL_UART_AbortReceive_IT(protocol->huart);
}

// 环形缓冲区写入
static void buffer_write(SerialProtocol_t *protocol, uint8_t byte)
{
    protocol->rx_buffer[protocol->rx_head] = byte;
    protocol->rx_head = (protocol->rx_head + 1) % RX_BUFFER_SIZE;
    // 如果缓冲区满了，移动tail指针（丢弃最旧的数据）
    if (protocol->rx_head == protocol->rx_tail)
    {
        protocol->rx_tail = (protocol->rx_tail + 1) % RX_BUFFER_SIZE;
    }
}

// 环形缓冲区读取
static uint8_t buffer_read(SerialProtocol_t *protocol, uint8_t *byte)
{
    if (protocol->rx_head == protocol->rx_tail)
    {
        return 0; // 缓冲区为空
    }
    *byte = protocol->rx_buffer[protocol->rx_tail];
    protocol->rx_tail = (protocol->rx_tail + 1) % RX_BUFFER_SIZE;
    return 1; // 成功读取
}

// 检查缓冲区是否有数据
static uint8_t buffer_available(SerialProtocol_t *protocol)
{
    return (protocol->rx_head != protocol->rx_tail);
}

// UART接收中断回调函数
void SerialProtocol_RxCallback(SerialProtocol_t *protocol)
{
    // 将接收到的字节存入环形缓冲区
    buffer_write(protocol, protocol->rx_byte);

    // 继续接收下一个字节
    HAL_UART_Receive_IT(protocol->huart, &protocol->rx_byte, 1);
}

// 打包并发送
int SerialProtocol_Send(SerialProtocol_t *protocol, const uint8_t *data, uint8_t data_len, uint32_t timeout)
{
    if (data_len > MAX_DATA_LENGTH)
        return -1;

    uint8_t frame[4 + MAX_DATA_LENGTH];
    frame[0] = FRAME_HEAD;
    frame[1] = data_len;
    for (uint8_t i = 0; i < data_len; ++i)
        frame[2 + i] = data[i];
    frame[2 + data_len] = calculate_checksum(&frame[1], 1 + data_len);
    frame[3 + data_len] = FRAME_TAIL;
    uint8_t frame_len = 4 + data_len;

    if (HAL_UART_Transmit(protocol->huart, frame, frame_len, timeout) == HAL_OK)
        return 0;
    return -1;
}

// 处理接收到的数据（在主循环中调用）
int SerialProtocol_Process(SerialProtocol_t *protocol)
{
    uint8_t byte;

    while (buffer_available(protocol))
    {
        if (!buffer_read(protocol, &byte))
            break;

        switch (protocol->rx_state)
        {
        case RX_STATE_IDLE: // 等待检测到帧头
            if (byte == FRAME_HEAD)
            {
                protocol->rx_state = RX_STATE_HEAD_FOUND;
                protocol->received_length = 0;
            }
            break;

        case RX_STATE_HEAD_FOUND: // 已检测到帧头，等待长度字节
            if (byte <= MAX_DATA_LENGTH)
            {
                protocol->expected_length = byte;
                protocol->rx_state = RX_STATE_LENGTH_RECEIVED;
            }
            else
            {
                protocol->rx_state = RX_STATE_IDLE; // 长度无效，重新开始
            }
            break;

        case RX_STATE_LENGTH_RECEIVED: // 已接收长度字节，准备接收数据
            if (protocol->expected_length == 0)
            {
                // 数据长度为0，直接检查校验和
                uint8_t expected_checksum = calculate_checksum(&protocol->expected_length, 1);
                if (byte == expected_checksum)
                {
                    protocol->rx_state = RX_STATE_DATA_RECEIVING; // 准备接收帧尾
                }
                else
                {
                    protocol->rx_state = RX_STATE_IDLE; // 校验失败，重新开始
                }
            }
            else
            {
                // 开始接收数据
                protocol->frame_data[protocol->received_length] = byte;
                protocol->received_length++;
                if (protocol->received_length >= protocol->expected_length)
                {
                    protocol->rx_state = RX_STATE_DATA_RECEIVING;
                }
            }
            break;

        case RX_STATE_DATA_RECEIVING: // 接收数据成功，等待校验和和帧尾
            if (protocol->received_length == protocol->expected_length)
            {
                // 接收校验和
                uint8_t expected_checksum = calculate_checksum(&protocol->expected_length, 1);
                expected_checksum += calculate_checksum(protocol->frame_data, protocol->expected_length);
                expected_checksum &= 0xFF;

                if (byte == expected_checksum)
                {
                    protocol->frame_checksum = byte;
                    // 准备接收帧尾
                    protocol->received_length++; // 标记已接收校验和
                }
                else
                {
                    protocol->rx_state = RX_STATE_IDLE; // 校验失败，重新开始
                }
            }
            else
            {
                // 接收帧尾
                if (byte == FRAME_TAIL)
                {
                    protocol->frame_length = protocol->expected_length;
                    protocol->frame_ready = 1;
                    protocol->rx_state = RX_STATE_FRAME_COMPLETE;
                    return 0; // 成功接收完整帧
                }
                else
                {
                    protocol->rx_state = RX_STATE_IDLE; // 帧尾错误，重新开始
                }
            }
            break;

        case RX_STATE_FRAME_COMPLETE:
            // 帧已完成，等待被读取
            break;
        }
    }

    return 1; // 无新完整帧
}

// 解包数据，并准备接收下一帧
int SerialProtocol_GetReceivedFrame(SerialProtocol_t *protocol, uint8_t *data, uint8_t *data_len)
{
    if (!protocol->frame_ready)
    {
        return -1; // 无可用数据
    }

    // 拷贝数据
    for (uint8_t i = 0; i < protocol->frame_length; ++i)
    {
        data[i] = protocol->frame_data[i];
    }
    *data_len = protocol->frame_length;

    // 清除标志，准备接收下一帧
    protocol->frame_ready = 0;
    protocol->rx_state = RX_STATE_IDLE;

    return 0; // 成功
}