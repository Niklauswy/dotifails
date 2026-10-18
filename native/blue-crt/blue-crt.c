/* Decorative GTK3 module for Slick Greeter. No authentication or input handling.
 * The entry changed signal only timestamps activity; text is never read. */
#include <gtk/gtk.h>
#include <math.h>
#include <string.h>
#include <stdio.h>

static GtkWidget *screen_widget;
static cairo_surface_t *tux, *tux_motion;
static gint64 started, activity;
static gboolean motion = TRUE;
static guint ticks;

static double seconds(void) { return (g_get_monotonic_time()-started)/1000000.0; }
static void color(cairo_t *cr, double v) { cairo_set_source_rgb(cr,v,v,v); }
static void rect(cairo_t *cr,double x,double y,double w,double h) { cairo_rectangle(cr,x,y,w,h);cairo_fill(cr); }

static gboolean panel_draw(GtkWidget *widget,cairo_t *cr,gpointer data) {
    (void)data;
    int w=gtk_widget_get_allocated_width(widget),h=gtk_widget_get_allocated_height(widget);
    if(w<20 || h<20)return FALSE;
    cairo_save(cr);
    cairo_set_antialias(cr,CAIRO_ANTIALIAS_NONE);
    color(cr,.025);rect(cr,7,7,w-7,h-7);
    color(cr,.67);rect(cr,0,0,w-7,h-7);
    color(cr,.94);rect(cr,2,2,w-11,2);rect(cr,2,2,2,h-11);
    color(cr,.22);rect(cr,2,h-11,w-9,2);rect(cr,w-11,2,2,h-9);
    color(cr,.45);rect(cr,5,5,w-17,1);rect(cr,5,5,1,h-17);
    color(cr,.86);rect(cr,5,h-14,w-17,1);rect(cr,w-14,5,1,h-17);
    double pulse=motion?exp(-(g_get_monotonic_time()-activity)/180000.0):0;
    cairo_set_source_rgba(cr,.05,.1,.8,pulse*.65);rect(cr,w-24,12,5,5);
    cairo_restore(cr);return FALSE;
}

static void edited(GtkEditable *entry,gpointer data) {
    (void)entry;(void)data;activity=g_get_monotonic_time();
}

static void decorate(GtkWidget *widget,gpointer data) {
    (void)data;
    const char *type=G_OBJECT_TYPE_NAME(widget);
    if(!g_object_get_data(G_OBJECT(widget),"blue-crt-hook")) {
        if(!strcmp(type,"DashBox"))
            g_signal_connect_after(widget,"draw",G_CALLBACK(panel_draw),NULL);
        if(GTK_IS_ENTRY(widget))
            g_signal_connect(widget,"changed",G_CALLBACK(edited),NULL);
        if(strstr(type,"PromptBox"))
            gtk_style_context_add_class(gtk_widget_get_style_context(widget),"crt-dialog");
        g_object_set_data(G_OBJECT(widget),"blue-crt-hook",GINT_TO_POINTER(1));
    }
    if(GTK_IS_CONTAINER(widget))gtk_container_forall(GTK_CONTAINER(widget),decorate,NULL);
}

/* Sample the generated atlas without rewriting or resampling its source PNG. */
static void mascot_frame(cairo_t *cr,int index,double size,double alpha) {
    double cell=cairo_image_surface_get_width(tux_motion)/4.0;
    double cell_h=cairo_image_surface_get_height(tux_motion)/2.0;
    cairo_save(cr);cairo_rectangle(cr,0,0,size,size);cairo_clip(cr);
    cairo_scale(cr,size/cell,size/cell_h);
    cairo_set_source_surface(cr,tux_motion,-(index%4)*cell,-(index/4)*cell_h);
    cairo_paint_with_alpha(cr,alpha);cairo_restore(cr);
}

static void mascot(cairo_t *cr,double size,double time) {
    if(tux_motion && cairo_surface_status(tux_motion)==CAIRO_STATUS_SUCCESS) {
        int from=0,to=0;double mix=0;
        if(motion) {
            const int wave[]={0,4,5,6,5,6,5,7,4,0};
            const int blink[]={0,1,2,1,0};
            double wave_time=fmod(time+13,15);
            double blink_time=fmod(time+1.1,5.9);
            if(wave_time<1.8) {
                double position=wave_time/.2;int k=MIN((int)position,8);
                from=wave[k];to=wave[k+1];mix=CLAMP((position-k)*2,0,1);
            } else if(blink_time<.36) {
                double position=blink_time/.09;int k=MIN((int)position,3);
                from=blink[k];to=blink[k+1];mix=position-k;
            } else {
                from=0;to=3;mix=(.5+.5*sin(time*1.25))*.3;
            }
            /* Feet stay anchored while the chest rises gently. */
            double breath=sin(time*1.25)*.006;
            cairo_translate(cr,0,-size*breath);cairo_scale(cr,1,1+breath);
        }
        cairo_push_group(cr);
        mascot_frame(cr,from,size,1-mix);
        if(mix>0) {
            cairo_set_operator(cr,CAIRO_OPERATOR_ADD);
            mascot_frame(cr,to,size,mix);
            cairo_set_operator(cr,CAIRO_OPERATOR_OVER);
        }
        cairo_pop_group_to_source(cr);cairo_paint(cr);
    } else if(tux && cairo_surface_status(tux)==CAIRO_STATUS_SUCCESS) {
        cairo_scale(cr,size/cairo_image_surface_get_width(tux),size/cairo_image_surface_get_height(tux));
        cairo_set_source_surface(cr,tux,0,0);cairo_paint(cr);
    }
}

static void glass(cairo_t *cr,int x,int y,int w,int h,double time) {
    cairo_save(cr);cairo_rectangle(cr,x,y,w,h);cairo_clip(cr);cairo_translate(cr,x,y);
    /* Mascot is composed at runtime: preserve the generated PNG and its alpha. */
    if(w>=650) {
        double size=MIN(h*.49,w*.30);
        cairo_save(cr);cairo_translate(cr,w*.77-size/2,h*.53-size/2);
        mascot(cr,size,time);cairo_restore(cr);
    }
    /* Shadow mask across the actual UI, not only the wallpaper. */
    cairo_set_antialias(cr,CAIRO_ANTIALIAS_NONE);
    cairo_set_source_rgba(cr,0,0,.025,.105);
    for(int yy=0;yy<h;yy+=3)cairo_rectangle(cr,0,yy,w,1);
    cairo_fill(cr);
    cairo_set_source_rgba(cr,.1,.4,1,.025);
    for(int xx=0;xx<w;xx+=3)cairo_rectangle(cr,xx,0,1,h);
    cairo_fill(cr);
    if(motion) {
        double band=fmod(time*.105,1.18)*h-h*.14;
        cairo_pattern_t *p=cairo_pattern_create_linear(0,band,0,band+h*.15);
        cairo_pattern_add_color_stop_rgba(p,0,.6,.8,1,0);
        cairo_pattern_add_color_stop_rgba(p,.65,.65,.82,1,.048);
        cairo_pattern_add_color_stop_rgba(p,1,.65,.82,1,0);
        cairo_set_source(cr,p);rect(cr,0,band,w,h*.15);cairo_pattern_destroy(p);
        /* Short, low amplitude sync disturbances; no white strobe. */
        double beat=fmod(time,9.7);
        if(beat>8.9 && beat<9.08) {
            cairo_set_source_rgba(cr,0,0,0,.045);cairo_paint(cr);
            cairo_set_source_rgba(cr,.45,.65,1,.12);rect(cr,0,h*.29,w,1);
        }
        for(int i=0;i<32;i++) {
            unsigned n=(unsigned)(time*18)*2654435761u+(unsigned)i*2246822519u;
            cairo_set_source_rgba(cr,.65,.8,1,.055);
            rect(cr,n%(unsigned)w,(n>>13)%(unsigned)h,2,1);
        }
    }
    cairo_set_antialias(cr,CAIRO_ANTIALIAS_DEFAULT);
    /* Curved glass falloff and a thin inner reflection. */
    cairo_pattern_t *v=cairo_pattern_create_radial(w*.5,h*.48,h*.22,w*.5,h*.48,h*.85);
    cairo_pattern_add_color_stop_rgba(v,0,0,0,0,0);
    cairo_pattern_add_color_stop_rgba(v,.65,0,0,.03,.03);
    cairo_pattern_add_color_stop_rgba(v,1,0,0,.02,.45);
    cairo_set_source(cr,v);cairo_paint(cr);cairo_pattern_destroy(v);
    cairo_set_source_rgba(cr,.55,.7,1,.16);cairo_set_line_width(cr,1);
    cairo_rectangle(cr,7.5,7.5,w-15,h-15);cairo_stroke(cr);
    /* Native startup reveal: collapse curtains toward the outer edges. */
    if(motion && time<.8) {
        double reveal=CLAMP(time/.8,0,1);reveal=1-pow(1-reveal,3);
        color(cr,0);double cover=(1-reveal)*h*.5;
        rect(cr,0,0,w,cover);rect(cr,0,h-cover,w,cover);
    }
    cairo_restore(cr);
}

static gboolean overlay(GtkWidget *widget,cairo_t *cr,gpointer data) {
    (void)data;
    double time=seconds();
    const char *preview=g_getenv("BLUE_CRT_PREVIEW_GEOMETRY");
    int pw=0,ph=0;
    if(preview && sscanf(preview,"%dx%d",&pw,&ph)==2 && pw>0 && ph>0) {
        glass(cr,0,0,pw,ph,time);return FALSE;
    }
    GdkDisplay *display=gtk_widget_get_display(widget);
    for(int i=0;i<gdk_display_get_n_monitors(display);i++) {
        GdkRectangle r;gdk_monitor_get_geometry(gdk_display_get_monitor(display,i),&r);
        glass(cr,r.x,r.y,r.width,r.height,time);
    }
    return FALSE;
}

static gboolean frame(gpointer data) {
    (void)data;
    if(!screen_widget || ticks++%15==0) {
        GList *windows=gtk_window_list_toplevels();
        for(GList *p=windows;p;p=p->next) {
            GtkWidget *w=p->data;
            if((!screen_widget || screen_widget==w) && gtk_widget_get_mapped(w) && gtk_widget_get_allocated_width(w)>500 && gtk_widget_get_allocated_height(w)>300) {
                if(!g_object_get_data(G_OBJECT(w),"blue-crt-window")) {
                    started=g_get_monotonic_time();
                    g_signal_connect_after(w,"draw",G_CALLBACK(overlay),NULL);
                    g_object_set_data(G_OBJECT(w),"blue-crt-window",GINT_TO_POINTER(1));
                    screen_widget=w;g_object_add_weak_pointer(G_OBJECT(w),(gpointer*)&screen_widget);
                }
                decorate(w,NULL);
            }
        }
        g_list_free(windows);
        g_object_get(gtk_settings_get_default(),"gtk-enable-animations",&motion,NULL);
        if(g_getenv("BLUE_CRT_REDUCED_MOTION"))motion=FALSE;
    }
    if(screen_widget && motion && gtk_widget_get_mapped(screen_widget))gtk_widget_queue_draw(screen_widget);
    return G_SOURCE_CONTINUE;
}

G_MODULE_EXPORT void gtk_module_init(gint *argc,gchar ***argv) {
    (void)argc;(void)argv;
    const char *assets=g_getenv("BLUE_CRT_ASSETS");
    if(!assets)assets="/usr/share/dotifails/blue-crt";
    gchar *file=g_build_filename(assets,"tux.png",NULL);
    tux=cairo_image_surface_create_from_png(file);g_free(file);
    file=g_build_filename(assets,"tux-motion.png",NULL);
    tux_motion=cairo_image_surface_create_from_png(file);g_free(file);
    GtkCssProvider *css=gtk_css_provider_new();
    gtk_css_provider_load_from_data(css,".crt-dialog label { color: #14141b; text-shadow: none; }",-1,NULL);
    gtk_style_context_add_provider_for_screen(gdk_screen_get_default(),GTK_STYLE_PROVIDER(css),800);
    g_object_unref(css);
    started=g_get_monotonic_time();activity=started-10000000;
    g_timeout_add(33,frame,NULL);
}
