// Created by EtherealTide on 2025/7/7.
#ifndef SERIAL_PROTOCOL_H
#define SERIAL_PROTOCOL_H

#include "stm32g4xx_hal.h" //这里根据MCU的型号进行调整, 这个是基于STM32G474RET6设计的
#include <stdint.h>

#define FRAME_HEAD 0xAA
#define FRAME_TAIL 0xBB
#define MAX_DATA_LENGTH 255
#define RX_BUFFER_SIZE 512 // 接收缓冲区大小

// 接收状态枚举
typedef enum
{
    RX_STATE_IDLE = 0,
    RX_STATE_HEAD_FOUND,
    RX_STATE_LENGTH_RECEIVED,
    RX_STATE_DATA_RECEIVING,
    RX_STATE_FRAME_COMPLETE
} RxState_t;

// 协议控制结构体
typedef struct
{
    UART_HandleTypeDef *huart;
    uint8_t rx_buffer[RX_BUFFER_SIZE];   // 环形缓冲区
    uint16_t rx_head;                    // 缓冲区头指针
    uint16_t rx_tail;                    // 缓冲区尾指针
    uint8_t rx_byte;                     // 接收单字节缓冲
    RxState_t rx_state;                  // 接收状态
    uint8_t expected_length;             // 期望接收的数据长度
    uint8_t received_length;             // 已接收的数据长度
    uint8_t frame_data[MAX_DATA_LENGTH]; // 当前帧数据
    uint8_t frame_length;                // 当前帧长度
    uint8_t frame_checksum;              // 当前帧校验和
    uint8_t frame_ready;                 // 帧准备就绪标志
} SerialProtocol_t;

// 初始化协议
void SerialProtocol_Init(SerialProtocol_t *protocol, UART_HandleTypeDef *huart);

// 启动接收（启用中断）
void SerialProtocol_StartReceive(SerialProtocol_t *protocol);

// 停止接收（禁用中断）
void SerialProtocol_StopReceive(SerialProtocol_t *protocol);

// 发送数据（自动打包并发送）
// 返回0成功，-1失败
int SerialProtocol_Send(SerialProtocol_t *protocol, const uint8_t *data, uint8_t data_len, uint32_t timeout);

// 处理接收到的数据（在主循环中调用）
// 返回0成功，-1失败，1无新数据
int SerialProtocol_Process(SerialProtocol_t *protocol);

// 获取接收到的帧数据
// 返回0成功，-1无可用数据
int SerialProtocol_GetReceivedFrame(SerialProtocol_t *protocol, uint8_t *data, uint8_t *data_len);

// UART接收中断回调函数（需要在HAL_UART_RxCpltCallback中调用）
void SerialProtocol_RxCallback(SerialProtocol_t *protocol);

#endif