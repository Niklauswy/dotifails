/* Wysun visuals only. Authentication and grabs remain upstream i3lock. */
#include <stdbool.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <ev.h>
#include <cairo.h>
#include <xcb/xcb.h>
#include "unlock_indicator.h"
#include "xcb.h"
extern struct ev_loop *main_loop;
extern xcb_window_t win;
extern unlock_state_t unlock_state;
extern auth_state_t auth_state;
static ev_timer motion;
static double entered=0, pressed=-10, failed=-10, leaving=0, phase=0;
static bool backwards=false, reduced=false, initialized=false, tokyo=false, space_black=false;
static double intro_seconds=.24,pulse_seconds=.24,exit_seconds=.20;
static xcb_atom_t opacity_atom=XCB_NONE;
static double clamp(double x) { return fmax(0,fmin(1,x)); }
static double ease(double x) { x=clamp(x);return 1-pow(1-x,3); }

static void frame(EV_P_ ev_timer *watcher,int events) {
    double now=ev_time();
    if (leaving>0) {
        double progress=clamp((now-leaving)/exit_seconds);
        /* Only reached after PAM success; grabs stay held until the last frame. */
        if (opacity_atom!=XCB_NONE) {
            uint32_t opacity=(uint32_t)((1-ease(progress))*UINT32_MAX);
            xcb_change_property(conn,XCB_PROP_MODE_REPLACE,win,opacity_atom,XCB_ATOM_CARDINAL,32,1,&opacity);
        }
        if (progress>=1) { ev_timer_stop(EV_A_ watcher);ev_break(EV_A_ EVBREAK_ALL);return; }
    }
    redraw_screen();
    if (leaving==0 && now-entered>.4 && now-pressed>.38 && now-failed>.46)
        ev_timer_stop(EV_A_ watcher);
}
static void animate(void) {
    if (!initialized)return;
    ev_timer_stop(main_loop,&motion);
    ev_timer_set(&motion,0,1./60);
    ev_timer_start(main_loop,&motion);
}
void orbit_motion_start(void) {
    reduced=getenv("ORBIT_REDUCED_MOTION") && atoi(getenv("ORBIT_REDUCED_MOTION"))!=0;
    tokyo=getenv("ORBIT_THEME") && strcmp(getenv("ORBIT_THEME"),"tokyo")==0;
    space_black=getenv("ORBIT_THEME") && strcmp(getenv("ORBIT_THEME"),"space-black")==0;
    intro_seconds=tokyo?.40:.24;pulse_seconds=tokyo?.38:.24;exit_seconds=tokyo?.32:.20;
    if (space_black) {intro_seconds=.28;pulse_seconds=.28;exit_seconds=.24;}
    entered=ev_time();
    ev_timer_init(&motion,frame,0,1./60);initialized=true;
    xcb_intern_atom_reply_t *reply=xcb_intern_atom_reply(conn,xcb_intern_atom(conn,0,22,"_NET_WM_WINDOW_OPACITY"),NULL);
    if (reply) { opacity_atom=reply->atom;free(reply); }
    animate();
}
void orbit_key_pulse(bool backspace) {
    pressed=ev_time();phase+=2.399963;backwards=backspace;animate();
}
void orbit_failure(void) { failed=ev_time();animate(); }
void orbit_unlock(void) {
    if (reduced) { ev_break(main_loop,EVBREAK_ALL);return; }
    leaving=ev_time();animate();
}
double orbit_intro_progress(void) {
    return reduced ? 1 : !initialized ? 0 : ease((ev_time()-entered)/intro_seconds);
}
void orbit_draw_indicator(cairo_t *ctx) {
    double now=ev_time(),age=now-pressed,exit=leaving>0?clamp((now-leaving)/exit_seconds):0;
    bool wrong=auth_state==STATE_AUTH_WRONG || auth_state==STATE_I3LOCK_LOCK_FAILED;
    double r=wrong?.93:tokyo?.73:.48,g=wrong?.56:tokyo?.60:.79,b=wrong?.61:tokyo?.97:.86;
    if (space_black && !wrong) {r=.81;g=.81;b=.83;}
    if (leaving>0) { r=.62;g=.87;b=.76; }
    double intro=orbit_intro_progress(),zoom=.96+.04*intro;
    cairo_save(ctx);cairo_translate(ctx,92,92);cairo_scale(ctx,zoom,zoom);
    if (wrong && !reduced) cairo_translate(ctx,sin((now-failed)*48)*6*(1-clamp((now-failed)/.46)),0);
    cairo_set_line_cap(ctx,CAIRO_LINE_CAP_ROUND);
    /* Quiet persistent orbit, no password-length display. */
    cairo_arc(ctx,0,0,54,0,2*M_PI);cairo_set_source_rgba(ctx,r,g,b,.13*intro);cairo_set_line_width(ctx,1.5);cairo_stroke(ctx);
    cairo_arc(ctx,0,0,42,0,2*M_PI);cairo_set_source_rgba(ctx,space_black?.12:tokyo?.15:.08,space_black?.12:tokyo?.11:.15,space_black?.13:tokyo?.21:.18,.45*intro);cairo_fill(ctx);
    if (age<pulse_seconds && !reduced && leaving==0) {
        double progress=clamp(age/pulse_seconds),fade=pow(1-progress,2),angle=phase+ease(progress)*.55;
        cairo_arc(ctx,0,0,56+ease(progress)*(tokyo?23:14),0,2*M_PI);cairo_set_source_rgba(ctx,r,g,b,.32*fade);cairo_set_line_width(ctx,1);cairo_stroke(ctx);
        cairo_arc(ctx,0,0,54,angle,angle+1.1);cairo_set_source_rgba(ctx,backwards?.95:r,backwards?.70:g,backwards?.57:b,.95*(1-progress));cairo_set_line_width(ctx,3);cairo_stroke(ctx);
    }
    if (auth_state==STATE_AUTH_VERIFY || leaving>0 || wrong) {
        cairo_arc(ctx,0,0,54,-M_PI/2,-M_PI/2+(leaving>0 ? 2*M_PI : wrong ? 2*M_PI : 1.5));
        cairo_set_source_rgba(ctx,r,g,b,.85*intro);cairo_set_line_width(ctx,2.5);cairo_stroke(ctx);
    }
    cairo_set_source_rgba(ctx,r,g,b,.88*intro);cairo_set_line_width(ctx,2);
    if (leaving>0) {
        cairo_move_to(ctx,-10,0);cairo_line_to(ctx,-3,7);cairo_line_to(ctx,12,-8);cairo_stroke(ctx);
    } else if (wrong) {
        cairo_move_to(ctx,-6,-6);cairo_line_to(ctx,6,6);cairo_move_to(ctx,6,-6);cairo_line_to(ctx,-6,6);cairo_stroke(ctx);
    } else {
        double lift=leaving>0?exit*8:0;
        cairo_arc(ctx,0,-5-lift,8,M_PI,2*M_PI);cairo_stroke(ctx);
        cairo_rectangle(ctx,-12,-5,24,20);cairo_stroke(ctx);
        cairo_move_to(ctx,0,3);cairo_line_to(ctx,0,8);cairo_stroke(ctx);
    }
    cairo_restore(ctx);
}
