"""
    Flowblade Movie Editor is a nonlinear video editor.
    Copyright 2012 Janne Liljeblad.

    This file is part of Flowblade Movie Editor <http://code.google.com/p/flowblade>.

    Flowblade Movie Editor is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Flowblade Movie Editor is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Flowblade Movie Editor.  If not, see <http://www.gnu.org/licenses/>.
"""
from gi.repository import Gdk
from gi.repository import Gtk

import cairo
import mlt
import os
import threading
import utils

import appconsts
import cairoarea
import editorstate
from editorstate import PLAYER
from editorstate import PROJECT

DEFAULT_VIEW = 0
START_TRIM_VIEW = 1
END_TRIM_VIEW = 2

MATCH_FRAME = "match_frame.png"

class MonitorWidget:
    
    def __init__(self):
        self.widget = Gtk.VBox()
        
        self.view = DEFAULT_VIEW
        self.match_frame_surface = None
        
        # top row
        self.top_row = Gtk.HBox()
        
        top = cairoarea.CairoDrawableArea2(1, 1, self._draw_black, use_widget_bg=False)
        self.top_row.pack_start(top, True, True,0)
        
        # mid row
        self.mid_row = Gtk.HBox()

        self.left_display = cairoarea.CairoDrawableArea2(1, 1, self._draw_match_frame, use_widget_bg=False)

        black_box = Gtk.EventBox()
        black_box.add(Gtk.Label())
        bg_color = Gdk.Color(red=0.0, green=0.0, blue=0.0)
        black_box.modify_bg(Gtk.StateType.NORMAL, bg_color)
        self.monitor = black_box

        self.right_display = cairoarea.CairoDrawableArea2(1, 1, self._draw_match_frame, use_widget_bg=False)
        
        self.mid_row.pack_start(self.left_display, False, False,0)
        self.mid_row.pack_start(self.monitor, True, True,0)
        self.mid_row.pack_start(self.right_display, False, False,0)
        
        # bottom row
        self.bottom_row = Gtk.HBox()
        bottom = cairoarea.CairoDrawableArea2(1, 1, self._draw_black, use_widget_bg=False)
        self.bottom_row.pack_start(bottom, True, True,0)
        
        # build pane
        self.widget.pack_start(self.top_row, False, False,0)
        self.widget.pack_start(self.mid_row , True, True,0)
        self.widget.pack_start(self.bottom_row, False, False,0)
        
    def get_monitor(self):
        return self.monitor

    def set_default_view(self):
        if self.view == DEFAULT_VIEW:
            return
        
        # Refreshing while rendering overwrites file on disk and loses 
        # previous rendered data. 
        if PLAYER().is_rendering:
            return

        self.view = DEFAULT_VIEW
        self.left_display.set_pref_size(1, 1)
        self.right_display.set_pref_size(1, 1)
        self.widget.queue_draw()
        PLAYER().refresh()
        
    def set_start_trim_view(self, match_clip):
        if editorstate.show_trim_view == False:
            return

        if self.view == START_TRIM_VIEW:
            # get trim match image
            return

        # Refreshing while rendering overwrites file on disk and loses 
        # previous rendered data. 
        if PLAYER().is_rendering:
            return
        
        self.view = START_TRIM_VIEW
        self.match_frame_surface = None

        print "jjajaj"
        self.left_display.set_pref_size(*self.get_match_frame_panel_size())
        self.right_display.set_pref_size(1, 1)
        self.widget.queue_draw()
        PLAYER().refresh()

        match_frame_write_thread = MonitorMatchFrameWriter(match_clip.path, match_clip.clip_out, 
                                                            MATCH_FRAME, self.match_frame_write_complete)
        match_frame_write_thread.start()

    def set_end_trim_view(self, match_clip):
        if editorstate.show_trim_view == False:
            return

        if self.view == END_TRIM_VIEW:
            # get trim match image
            return

        # Refreshing while rendering overwrites file on disk and loses 
        # previous rendered data. 
        if PLAYER().is_rendering:
            return
        
        self.view = END_TRIM_VIEW
        self.match_frame_surface = None
        
        print "jjajaj"
        self.left_display.set_pref_size(1, 1)
        self.right_display.set_pref_size(*self.get_match_frame_panel_size())
        self.widget.queue_draw()
        PLAYER().refresh()
        
        match_frame_write_thread = MonitorMatchFrameWriter(match_clip.path, match_clip.clip_in, 
                                                            MATCH_FRAME, self.match_frame_write_complete)
        match_frame_write_thread.start()

    def _draw_match_frame(self, event, cr, allocation):
        x, y, w, h = allocation

        if self.match_frame_surface == None:
            # Draw black
            cr.set_source_rgb(0.0, 0.0, 0.0)
            cr.rectangle(0, 0, w, h)
            cr.fill()
        else:
            # Draw match frame
            cr.set_source_surface(self.match_frame_surface, 0, 0)
            cr.paint()
            
    def _draw_black(self, event, cr, allocation):
        x, y, w, h = allocation

        # Draw bg
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.rectangle(0, 0, w, h)
        cr.fill()

    def _draw_red(self, event, cr, allocation):
        # testing
        x, y, w, h = allocation

        # Draw bg
        cr.set_source_rgb(1.0, 0.0, 0.0)
        cr.rectangle(0, 0, w, h)
        cr.fill()
    
    def get_match_frame_panel_size(self):
        monitor_alloc = self.widget.get_allocation()
        inv_profile_screen_ratio = float(PROJECT().profile.height()) / float(PROJECT().profile.width())
        return (int(monitor_alloc.width/2), int(inv_profile_screen_ratio * monitor_alloc.width/2))
        
    def match_frame_write_complete(self, frame_name):
        self.match_frame_surface = self.create_match_frame_image_surface(frame_name)
        self.left_display.queue_draw()
        self.right_display.queue_draw()

    def create_match_frame_image_surface(self, frame_name):
        # Create non-scaled surface
        matchframe_path = utils.get_hidden_user_dir_path() + appconsts.TRIM_VIEW_DIR + "/" + frame_name 
        
        surface = cairo.ImageSurface.create_from_png(matchframe_path)

        # Create and return scaled surface
        profile_screen_ratio = float(PROJECT().profile.width()) / float(PROJECT().profile.height())
        match_frame_width, match_frame_height = self.get_match_frame_panel_size()
        
        print  match_frame_width, match_frame_height, surface.get_width(), surface.get_height()
        scaled_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(match_frame_width), int(match_frame_height))
        cr = cairo.Context(scaled_surface)
        cr.scale(float(match_frame_width) / float(surface.get_width()), float(match_frame_height) / float(surface.get_height()))

        cr.set_source_surface(surface, 0, 0)
        cr.paint()
        
        return scaled_surface
        

class MonitorMatchFrameWriter(threading.Thread):
    def __init__(self, clip_path, clip_frame, frame_name, completion_callback):
        self.clip_path = clip_path
        self.clip_frame = clip_frame
        self.completion_callback = completion_callback
        self.frame_name = frame_name
        threading.Thread.__init__(self)
        
    def run(self):
        """
        Writes thumbnail image from file producer
        """
        print "kkkkkkkkkkkkk"
        # Create consumer
        matchframe_path = utils.get_hidden_user_dir_path() + appconsts.TRIM_VIEW_DIR + "/" + self.frame_name
        consumer = mlt.Consumer(PROJECT().profile, "avformat", matchframe_path)
        consumer.set("real_time", 0)
        consumer.set("vcodec", "png")

        # Create one frame producer
        producer = mlt.Producer(PROJECT().profile, str(self.clip_path))
        producer = producer.cut(int(self.clip_frame), int(self.clip_frame))

        # Delete match frame
        try:
            os.remove(matchframe_path)
        except:
            # This fails when done first time ever  
            pass
            
        # Connect and write image
        consumer.connect(producer)
        consumer.run()
        
        # Wait until new file exists
        while os.path.isfile(matchframe_path) != True:
            time.sleep(0.1)

        # Do completion callback
        self.completion_callback(self.frame_name)

        
