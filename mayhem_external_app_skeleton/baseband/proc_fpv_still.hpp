/*
 * FPV Still synthetic line-stream baseband plumbing test.
 */

#ifndef __PROC_FPV_STILL_H__
#define __PROC_FPV_STILL_H__

#include "baseband_processor.hpp"
#include "thread_base.hpp"

#include <cstdint>

class FPVStillSynthetic : public BasebandProcessor {
   public:
    FPVStillSynthetic();
    ~FPVStillSynthetic() override;

    void execute(const buffer_c8_t& buffer) override;
    void on_message(const Message* const message) override;

    FPVStillSynthetic(const FPVStillSynthetic&) = delete;
    FPVStillSynthetic(FPVStillSynthetic&&) = delete;
    FPVStillSynthetic& operator=(const FPVStillSynthetic&) = delete;
    FPVStillSynthetic& operator=(FPVStillSynthetic&&) = delete;

   private:
    class ProducerThread : public ThreadBase {
       public:
        explicit ProducerThread(FPVStillSynthetic& owner);
        ~ProducerThread() override;

        ProducerThread(const ProducerThread&) = delete;
        ProducerThread(ProducerThread&&) = delete;
        ProducerThread& operator=(const ProducerThread&) = delete;
        ProducerThread& operator=(ProducerThread&&) = delete;

        void start() override;
        void stop();

       private:
        FPVStillSynthetic& owner_;
        Thread* thread_{nullptr};

        void run() override;
    };

    static constexpr uint16_t width = 160;
    static constexpr uint16_t height = 120;
    static constexpr size_t fifo_packet_count = 1 << FPVStillLineConfigMessage::fifo_k;

    static_assert(fifo_packet_count == 8, "FPV Still test FIFO should stay small");

    void configure(const FPVStillConfigMessage& message);
    void publish_fifo();
    void produce_packet();
    bool produce_until_full();
    void notify_lines_ready();
    void fill_synthetic_line(FPVStillLinePacket& packet, uint8_t slot, uint8_t y, uint16_t frame_id);

    FPVStillLinePacket fifo_data[fifo_packet_count]{};
    FPVStillLineFIFO fifo{fifo_data, FPVStillLineConfigMessage::fifo_k};
    ProducerThread producer_;

    volatile bool running_{false};
    uint16_t frame_id_{0};
    uint8_t next_y_{0};
    uint16_t dropped_lines_{0};
    uint32_t frame_start_ms_{0};
    uint32_t producer_frame_ms_{0};
    uint32_t last_notify_ms_{0};
};

#endif /*__PROC_FPV_STILL_H__*/
