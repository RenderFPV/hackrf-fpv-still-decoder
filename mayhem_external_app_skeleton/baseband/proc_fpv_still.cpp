/*
 * FPV Still synthetic line-stream baseband plumbing test.
 *
 * This processor intentionally does not create a BasebandThread. It never
 * enables SGPIO/DMA receive and never consumes RF samples.
 */

#include "proc_fpv_still.hpp"

#include "event_m4.hpp"
#include "portapack_shared_memory.hpp"

#include <ch.h>
#include <memory>

static WORKING_AREA(fpv_still_producer_wa, 1024);

FPVStillSynthetic::ProducerThread::ProducerThread(FPVStillSynthetic& owner)
    : owner_{owner} {
}

FPVStillSynthetic::ProducerThread::~ProducerThread() {
    stop();
}

void FPVStillSynthetic::ProducerThread::start() {
    if (!thread_) {
        thread_ = chThdCreateStatic(
            fpv_still_producer_wa,
            sizeof(fpv_still_producer_wa),
            NORMALPRIO,
            ThreadBase::fn,
            this);
    }
}

void FPVStillSynthetic::ProducerThread::stop() {
    if (thread_) {
        chThdTerminate(thread_);
        chThdWait(thread_);
        thread_ = nullptr;
    }
}

void FPVStillSynthetic::ProducerThread::run() {
    while (!chThdShouldTerminate()) {
        if (owner_.running_) {
            if (!owner_.produce_until_full()) {
                chThdSleepMilliseconds(1);
            } else {
                chThdYield();
            }
        } else {
            chThdSleepMilliseconds(25);
        }
    }
}

FPVStillSynthetic::FPVStillSynthetic()
    : producer_{*this} {
}

FPVStillSynthetic::~FPVStillSynthetic() {
    running_ = false;
    producer_.stop();
}

void FPVStillSynthetic::execute(const buffer_c8_t& buffer) {
    (void)buffer;
}

void FPVStillSynthetic::on_message(const Message* const message) {
    switch (message->id) {
        case Message::ID::FPVStillConfigure:
            configure(*reinterpret_cast<const FPVStillConfigMessage*>(message));
            break;

        default:
            break;
    }
}

void FPVStillSynthetic::configure(const FPVStillConfigMessage& message) {
    running_ = message.run;
    fifo.reset();
    next_y_ = 0;
    frame_id_ = 0;
    dropped_lines_ = 0;
    frame_start_ms_ = chTimeNow();
    producer_frame_ms_ = 0;
    last_notify_ms_ = 0;

    if (running_) {
        publish_fifo();
        producer_.start();
    }
}

void FPVStillSynthetic::publish_fifo() {
    FPVStillLineConfigMessage message{&fifo};
    shared_memory.application_queue.push(message);
}

void FPVStillSynthetic::produce_packet() {
    FPVStillLinePacket packet{};
    packet.frame_id = frame_id_;
    packet.dropped_lines = dropped_lines_;
    packet.y_start = next_y_;
    packet.line_count = static_cast<uint8_t>((next_y_ + 1 < height) ? 2 : 1);
    packet.producer_frame_ms = producer_frame_ms_;
    packet.flags = 0;

    if (next_y_ == 0) {
        frame_start_ms_ = chTimeNow();
    }

    for (uint8_t slot = 0; slot < packet.line_count; slot++) {
        fill_synthetic_line(packet, slot, static_cast<uint8_t>(next_y_ + slot), frame_id_);
    }

    const bool completes_frame = (next_y_ + packet.line_count) >= height;
    if (completes_frame) {
        packet.flags = 1;
        packet.producer_frame_ms = chTimeNow() - frame_start_ms_;
    }

    if (!fifo.in(packet)) {
        dropped_lines_++;
        return;
    }

    next_y_ += packet.line_count;
    if (next_y_ >= height) {
        next_y_ = 0;
        producer_frame_ms_ = packet.producer_frame_ms;
        frame_id_++;
    }
}

bool FPVStillSynthetic::produce_until_full() {
    bool produced = false;
    while (running_ && !fifo.is_full()) {
        produce_packet();
        produced = true;
    }

    if (produced || !fifo.is_empty()) {
        notify_lines_ready();
    }
    return produced;
}

void FPVStillSynthetic::notify_lines_ready() {
    const auto now = chTimeNow();
    if ((last_notify_ms_ == 0) || ((now - last_notify_ms_) >= 100)) {
        FPVStillLineReadyMessage message{};
        shared_memory.application_queue.push(message);
        last_notify_ms_ = now;
    }
}

void FPVStillSynthetic::fill_synthetic_line(FPVStillLinePacket& packet, uint8_t slot, uint8_t y, uint16_t frame_id) {
    const uint8_t bar_x = static_cast<uint8_t>((frame_id * 3) % width);
    const uint16_t pixel_offset = static_cast<uint16_t>(slot) * width;
    for (uint16_t x = 0; x < width; x++) {
        uint8_t level = static_cast<uint8_t>((x * 255) / (width - 1));

        if (((x / 16) + (y / 16)) & 1) {
            level = static_cast<uint8_t>((level * 3) / 4);
        }

        if ((x >= bar_x) && (x < static_cast<uint16_t>(bar_x + 6))) {
            level = 255;
        }

        if ((y == 0) || (y == height - 1) || (x == 0) || (x == width - 1)) {
            level = 255;
        }

        packet.pixels[pixel_offset + x] = level;
    }
}

int main() {
    EventDispatcher event_dispatcher{std::make_unique<FPVStillSynthetic>()};
    event_dispatcher.run();
    return 0;
}
