#import <ScreenSaver/ScreenSaver.h>
@interface KlanglaborScreenSaver : ScreenSaverView
@property(strong) NSImage *artwork;
@end
@implementation KlanglaborScreenSaver
- (instancetype)initWithFrame:(NSRect)frame isPreview:(BOOL)preview {
    self = [super initWithFrame:frame isPreview:preview];
    if (self) {
        NSURL *url = [[NSBundle bundleForClass:[self class]] URLForResource:@"wallpaper" withExtension:@"png"];
        self.artwork = [[NSImage alloc] initWithContentsOfURL:url];
        [self setAnimationTimeInterval:30.0];
    }
    return self;
}
- (void)startAnimation { [super startAnimation]; [self setNeedsDisplay:YES]; }
- (void)animateOneFrame { }
- (BOOL)isOpaque { return YES; }
- (void)drawRect:(NSRect)dirtyRect {
    [[NSColor colorWithSRGBRed:250.0/255 green:248.0/255 blue:242.0/255 alpha:1] setFill];
    NSRectFill(self.bounds);
    if (!self.artwork) return;
    NSSize size = self.artwork.size;
    CGFloat scale = MIN(NSWidth(self.bounds)/size.width, NSHeight(self.bounds)/size.height);
    NSRect target = NSMakeRect((NSWidth(self.bounds)-size.width*scale)/2,
                              (NSHeight(self.bounds)-size.height*scale)/2,
                              size.width*scale, size.height*scale);
    [self.artwork drawInRect:target fromRect:NSZeroRect operation:NSCompositingOperationCopy fraction:1
             respectFlipped:YES hints:@{NSImageHintInterpolation:@(NSImageInterpolationHigh)}];
}
@end
