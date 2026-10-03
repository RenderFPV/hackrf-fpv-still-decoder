/*
 * FPV Still external app for PortaPack Mayhem.
 *
 * M4 plumbing test: packaged baseband sends synthetic preview lines only.
 * No live RF receive is enabled by the UI.
 */

#include "ui.hpp"
#include "ui_fpv_still.hpp"
#include "ui_navigation.hpp"
#include "external_app.hpp"

namespace ui::external_app::fpv_still {
void initialize_app(ui::NavigationView& nav) {
    nav.push<FPVStillView>();
}
}  // namespace ui::external_app::fpv_still

extern "C" {

__attribute__((section(".external_app.app_fpv_still.application_information"), used)) application_information_t _application_information_fpv_still = {
    /*.memory_location = */ (uint8_t*)0x00000000,
    /*.externalAppEntry = */ ui::external_app::fpv_still::initialize_app,
    /*.header_version = */ CURRENT_HEADER_VERSION,
    /*.app_version = */ VERSION_MD5,

    /*.app_name = */ "FPV Still",
    /*.bitmap_data = */ {
        0x00,
        0x00,
        0x3C,
        0x3C,
        0x42,
        0x42,
        0x99,
        0x99,
        0xA5,
        0xA5,
        0x81,
        0x81,
        0xBD,
        0xBD,
        0x81,
        0x81,
        0xA5,
        0xA5,
        0x99,
        0x99,
        0x42,
        0x42,
        0x3C,
        0x3C,
        0x00,
        0x00,
        0x7E,
        0x7E,
        0x00,
        0x00,
        0x00,
        0x00,
    },
    /*.icon_color = */ ui::Color::orange().v,
    /*.menu_location = */ app_location_t::RX,
    /*.desired_menu_position = */ -1,

    /*.m4_app_tag = FPV Still synthetic plumbing */ {'P', 'F', 'P', 'V'},
    /*.m4_app_offset = */ 0x00000000,
};
}
