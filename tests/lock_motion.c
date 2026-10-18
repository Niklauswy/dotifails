#include <stdio.h>
#include <stdbool.h>
#include <xcb/xcb.h>
#include <ev.h>
#include <cairo.h>
#include "unlock_indicator.h"
#include "xcb.h"
struct ev_loop *main_loop;
xcb_window_t win=0;
xcb_connection_t *conn=NULL;
unlock_state_t unlock_state=STATE_STARTED;
auth_state_t auth_state=STATE_AUTH_IDLE;
void redraw_screen(void) {}
static double clock_value=10;
static double fake_time(void) {return clock_value;}
#define ev_time fake_time
#include "../native/orbit-lock/orbit_motion.c"
int main(void) {
    main_loop=EV_DEFAULT;initialized=true;entered=9;pressed=10;
    ev_timer_init(&motion,frame,0,1./60);
    /* Authentication failure must never initiate an exit. */
    auth_state=STATE_AUTH_WRONG;orbit_failure();if(leaving!=0)return 2;
    /* Successful exit remains active before the final 280 ms frame. */
    auth_state=STATE_AUTH_IDLE;orbit_unlock();double started=leaving;
    clock_value=started+exit_seconds*.7;frame(main_loop,&motion,0);if(!ev_is_active(&motion))return 3;
    clock_value=started+exit_seconds+.01;frame(main_loop,&motion,0);if(ev_is_active(&motion))return 4;
    reduced=true;clock_value+=1;orbit_unlock();
    return 0;
}
