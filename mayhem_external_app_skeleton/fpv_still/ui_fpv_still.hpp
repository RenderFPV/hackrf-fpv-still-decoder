/*
 * FPV Still placeholder UI for PortaPack Mayhem.
 *
 * Lightweight FPV Still UI. The M4 plumbing test streams synthetic grayscale
 * line packets through an M4-owned FIFO. No RF receive is enabled here.
 */

#ifndef __UI_FPV_STILL_H__
#define __UI_FPV_STILL_H__

#include <cstdint>

#include "message.hpp"
#include "ui.hpp"
#include "ui_navigation.hpp"
#include "ui_widget.hpp"

namespace ui::external_app::fpv_still {

class FPVStillView : public View {
   public:
    explicit FPVStillView(NavigationView& nav);
    ~FPVStillView();

    FPVStillView(const FPVStillView&) = delete;
    FPVStillView(FPVStillView&&) = delete;
    FPVStillView& operator=(const FPVStillView&) = delete;
    FPVStillView& operator=(FPVStillView&&) = delete;

    void focus() override;
    void paint(Painter& painter) override;

    std::string title() const override { return "FPV Still"; };

   private:
    struct RacebandChannel {
        const char* label;
        int32_t nominal_mhz;
    };

    static constexpr RacebandChannel raceband_channels[8] = {
        {"R1", 5658},
        {"R2", 5695},
        {"R3", 5732},
        {"R4", 5769},
        {"R5", 5806},
        {"R6", 5843},
        {"R7", 5880},
        {"R8", 5917},
    };

    void draw_test_pattern();
    uint32_t draw_fpv_packet(const FPVStillLinePacket& packet);
    void drain_line_fifo();
    void start_streaming();
    void stop_streaming();
    void update_tuned_frequency();
    void update_status_text();
    void rebuild_luma_palette();
    void ensure_luma_palette();
    uint8_t adjust_luma(uint8_t level) const;

    NavigationView& nav_;
    FPVStillLineFIFO* line_fifo_{nullptr};
    uint32_t line_count_{0};
    uint16_t frame_id_{0};
    uint16_t dropped_lines_{0};
    uint32_t frame_start_ms_{0};
    uint32_t frame_draw_accum_ms_{0};
    uint32_t frame_drain_accum_ms_{0};
    uint32_t last_frame_complete_ms_{0};
    uint32_t last_producer_ms_{0};
    uint32_t last_frame_ms_{0};
    uint32_t last_drain_ms_{0};
    uint32_t last_draw_ms_{0};
    bool frame_complete_pending_{false};
    bool preview_has_stream_{false};
    bool palette_dirty_{true};
    bool active_{false};
    bool streaming_started_{false};
    static constexpr uint8_t drain_packet_budget = 16;
    ui::Color line_buffer_[160]{};

    Labels labels{
        {{UI_POS_X(0), UI_POS_Y(0)}, "CH", Theme::getInstance()->fg_light->foreground},
        {{UI_POS_X(6), UI_POS_Y(0)}, "FINE", Theme::getInstance()->fg_light->foreground},
        {{UI_POS_X(16), UI_POS_Y(0)}, "GAIN", Theme::getInstance()->fg_light->foreground},
        {{UI_POS_X(0), UI_POS_Y(1)}, "ALIGN", Theme::getInstance()->fg_light->foreground},
        {{UI_POS_X(11), UI_POS_Y(1)}, "BRT", Theme::getInstance()->fg_light->foreground},
        {{UI_POS_X(19), UI_POS_Y(1)}, "CON", Theme::getInstance()->fg_light->foreground},
        {{UI_POS_X(0), UI_POS_Y(2)}, "SIZE", Theme::getInstance()->fg_light->foreground},
    };

    OptionsField field_channel{
        {UI_POS_X(3), UI_POS_Y(0)},
        2,
        {
            {"R1", 5658},
            {"R2", 5695},
            {"R3", 5732},
            {"R4", 5769},
            {"R5", 5806},
            {"R6", 5843},
            {"R7", 5880},
            {"R8", 5917},
        }};

    NumberField field_fine_mhz{
        {UI_POS_X(11), UI_POS_Y(0)},
        4,
        {-10, 10},
        1,
        ' '};

    OptionsField field_gain{
        {UI_POS_X(21), UI_POS_Y(0)},
        4,
        {
            {"LOW ", 0},
            {"MID ", 1},
            {"HIGH", 2},
            {"AUTO", 3},
        }};

    OptionsField field_align{
        {UI_POS_X(6), UI_POS_Y(1)},
        4,
        {
            {"AUTO", 0},
            {"-   ", -1},
            {"+   ", 1},
        }};

    NumberField field_brightness{
        {UI_POS_X(15), UI_POS_Y(1)},
        3,
        {-9, 9},
        1,
        ' '};

    NumberField field_contrast{
        {UI_POS_X(23), UI_POS_Y(1)},
        3,
        {-9, 9},
        1,
        ' '};

    OptionsField field_size{
        {UI_POS_X(5), UI_POS_Y(2)},
        3,
        {
            {"160", 160},
        }};

    Text text_tuned{
        {UI_POS_X(9), UI_POS_Y(2), UI_POS_WIDTH(21), UI_POS_DEFAULT_HEIGHT},
        ""};

    Text text_status{
        {UI_POS_X(0), UI_POS_Y(3), UI_POS_WIDTH(30), UI_POS_DEFAULT_HEIGHT},
        "M4 WAIT"};

    MessageHandlerRegistration message_handler_fpv_still_line_config{
        Message::ID::FPVStillLineConfig,
        [this](const Message* const p) {
            if (!active_) {
                return;
            }
            const auto message = *reinterpret_cast<const FPVStillLineConfigMessage*>(p);
            line_fifo_ = message.fifo;
            line_count_ = 0;
            frame_id_ = 0;
            dropped_lines_ = 0;
            preview_has_stream_ = false;
            last_frame_complete_ms_ = 0;
            update_status_text();
        }};

    MessageHandlerRegistration message_handler_frame_sync{
        Message::ID::DisplayFrameSync,
        [this](const Message* const) {
            drain_line_fifo();
        }};

    MessageHandlerRegistration message_handler_line_ready{
        Message::ID::FPVStillLineReady,
        [this](const Message* const) {
            drain_line_fifo();
        }};
};

}  // namespace ui::external_app::fpv_still

#endif /*__UI_FPV_STILL_H__*/
