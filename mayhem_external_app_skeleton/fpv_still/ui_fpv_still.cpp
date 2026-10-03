/*
 * FPV Still placeholder UI for PortaPack Mayhem.
 */

#include "ui_fpv_still.hpp"

#include "baseband_api.hpp"
#include "portapack.hpp"

#include <ch.h>
#include <cstdio>

using namespace portapack;

namespace ui::external_app::fpv_still {

static constexpr Coord preview_x = 40;
static constexpr Coord preview_y = 80;
static constexpr Dim preview_w = 160;
static constexpr Dim preview_h = 120;

static ui::Color luma_palette[256]{};

FPVStillView::FPVStillView(NavigationView& nav)
    : nav_{nav} {
    add_children({&labels,
                  &field_channel,
                  &field_fine_mhz,
                  &field_gain,
                  &field_align,
                  &field_brightness,
                  &field_contrast,
                  &field_size,
                  &text_tuned,
                  &text_status});

    field_channel.set_selected_index(4, false);
    field_fine_mhz.set_value(-4, false);
    field_gain.set_selected_index(1, false);
    field_align.set_selected_index(0, false);
    field_size.set_selected_index(0, false);

    field_channel.on_change = [this](size_t, OptionsField::value_t) {
        update_tuned_frequency();
    };
    field_fine_mhz.on_change = [this](int32_t) {
        update_tuned_frequency();
    };
    field_brightness.on_change = [this](int32_t) {
        palette_dirty_ = true;
        set_dirty();
    };
    field_contrast.on_change = [this](int32_t) {
        palette_dirty_ = true;
        set_dirty();
    };

    update_tuned_frequency();
    update_status_text();
}

FPVStillView::~FPVStillView() {
    stop_streaming();
}

void FPVStillView::focus() {
    field_channel.focus();
}

void FPVStillView::paint(Painter& painter) {
    View::paint(painter);

    painter.fill_rectangle({preview_x - 1, preview_y - 1, preview_w + 2, preview_h + 2}, Theme::getInstance()->bg_darkest->background);
    painter.draw_rectangle({preview_x - 1, preview_y - 1, preview_w + 2, preview_h + 2}, Theme::getInstance()->fg_light->foreground);
    if (!preview_has_stream_) {
        draw_test_pattern();
    }

    active_ = true;
    start_streaming();
}

void FPVStillView::start_streaming() {
    if (streaming_started_) {
        return;
    }

    baseband::run_prepared_image(portapack::memory::map::m4_code.base());
    baseband::set_fpv_still_config(true);
    streaming_started_ = true;
}

void FPVStillView::stop_streaming() {
    active_ = false;
    line_fifo_ = nullptr;

    if (streaming_started_) {
        baseband::set_fpv_still_config(false);
        baseband::shutdown();
        streaming_started_ = false;
    }
}

void FPVStillView::update_tuned_frequency() {
    const auto channel_index = field_channel.selected_index();
    const auto nominal_mhz = raceband_channels[channel_index].nominal_mhz;
    const auto tuned_mhz = nominal_mhz + field_fine_mhz.value();

    char buf[32];
    std::snprintf(buf, sizeof(buf), "%s %ld MHz -> %ld MHz",
                  raceband_channels[channel_index].label,
                  static_cast<long>(nominal_mhz),
                  static_cast<long>(tuned_mhz));
    text_tuned.set(buf);
}

uint8_t FPVStillView::adjust_luma(uint8_t level) const {
    const int32_t brightness = field_brightness.value() * 6;
    const int32_t contrast = 64 + field_contrast.value() * 4;
    int32_t adjusted = ((static_cast<int32_t>(level) - 128) * contrast) / 64 + 128 + brightness;

    if (adjusted < 0) {
        adjusted = 0;
    } else if (adjusted > 255) {
        adjusted = 255;
    }

    return static_cast<uint8_t>(adjusted);
}

void FPVStillView::rebuild_luma_palette() {
    for (uint16_t level = 0; level < 256; level++) {
        const auto adjusted = adjust_luma(static_cast<uint8_t>(level));
        luma_palette[level] = ui::Color{adjusted, adjusted, adjusted};
    }
    palette_dirty_ = false;
}

void FPVStillView::ensure_luma_palette() {
    if (palette_dirty_) {
        rebuild_luma_palette();
    }
}

void FPVStillView::draw_test_pattern() {
    ensure_luma_palette();

    for (Coord y = 0; y < preview_h; y++) {
        for (Coord x = 0; x < preview_w; x++) {
            uint8_t level = static_cast<uint8_t>((x * 255) / (preview_w - 1));

            if (((x / 16) + (y / 16)) & 1) {
                level = static_cast<uint8_t>((level * 3) / 4);
            }

            if (y < 10) {
                level = static_cast<uint8_t>(32 + (y * 12));
            }

            if ((x == 0) || (x == preview_w - 1) || (y == 0) || (y == preview_h - 1)) {
                level = 255;
            }

            line_buffer_[x] = luma_palette[level];
        }

        display.render_line({preview_x, static_cast<Coord>(preview_y + y)}, preview_w, line_buffer_);
    }
}

uint32_t FPVStillView::draw_fpv_packet(const FPVStillLinePacket& packet) {
    if (!active_) {
        return 0;
    }

    if ((packet.y_start >= preview_h) || (packet.line_count == 0) || (packet.line_count > 2)) {
        return 0;
    }

    ensure_luma_palette();

    const auto draw_start = chTimeNow();
    preview_has_stream_ = true;
    const uint8_t draw_lines = static_cast<uint8_t>(
        ((packet.y_start + packet.line_count) > preview_h) ? (preview_h - packet.y_start) : packet.line_count);

    if (packet.y_start == 0) {
        frame_start_ms_ = draw_start;
        frame_draw_accum_ms_ = 0;
        frame_drain_accum_ms_ = 0;
        frame_complete_pending_ = false;
    }

    for (uint8_t row = 0; row < draw_lines; row++) {
        const uint16_t pixel_offset = static_cast<uint16_t>(row) * preview_w;
        for (Coord x = 0; x < preview_w; x++) {
            line_buffer_[x] = luma_palette[packet.pixels[pixel_offset + x]];
        }

        display.render_line({preview_x, static_cast<Coord>(preview_y + packet.y_start + row)}, preview_w, line_buffer_);
    }

    const auto draw_end = chTimeNow();
    frame_draw_accum_ms_ += draw_end - draw_start;

    line_count_ += draw_lines;
    frame_id_ = packet.frame_id;
    dropped_lines_ = packet.dropped_lines;
    last_producer_ms_ = packet.producer_frame_ms;

    if ((packet.flags != 0) || ((packet.y_start + draw_lines) >= preview_h)) {
        last_frame_ms_ = (last_frame_complete_ms_ == 0) ? (draw_end - frame_start_ms_) : (draw_end - last_frame_complete_ms_);
        last_frame_complete_ms_ = draw_end;
        last_draw_ms_ = frame_draw_accum_ms_;
        frame_complete_pending_ = true;
    }

    return draw_end - draw_start;
}

void FPVStillView::drain_line_fifo() {
    if (!active_) {
        return;
    }

    if (!line_fifo_) {
        return;
    }

    const auto drain_start = chTimeNow();
    FPVStillLinePacket packet{};
    uint8_t drained = 0;
    uint32_t draw_ticks = 0;
    while ((drained < drain_packet_budget) && line_fifo_->out(packet)) {
        draw_ticks += draw_fpv_packet(packet);
        drained++;
    }
    const auto drain_elapsed = chTimeNow() - drain_start;
    frame_drain_accum_ms_ += (drain_elapsed > draw_ticks) ? (drain_elapsed - draw_ticks) : 0;

    if (frame_complete_pending_) {
        last_drain_ms_ = frame_drain_accum_ms_;
        frame_complete_pending_ = false;
        update_status_text();
    }
}

void FPVStillView::update_status_text() {
    char buf[32];
    if (!line_fifo_) {
        std::snprintf(buf, sizeof(buf), "M4 WAIT");
    } else {
        std::snprintf(buf, sizeof(buf), "P%lu W%lu R%lu U%lu",
                      static_cast<unsigned long>(last_producer_ms_),
                      static_cast<unsigned long>(last_frame_ms_),
                      static_cast<unsigned long>(last_drain_ms_),
                      static_cast<unsigned long>(last_draw_ms_));
    }
    text_status.set(buf);
}

}  // namespace ui::external_app::fpv_still
