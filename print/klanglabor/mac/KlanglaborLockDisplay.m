#import <Cocoa/Cocoa.h>
#import <IOKit/pwr_mgt/IOPMLib.h>
#import <CoreGraphics/CoreGraphics.h>

@interface KlanglaborLockDisplay : NSObject
@property BOOL locked;
@property IOPMAssertionID displayAssertion;
@property IOPMAssertionID sleepAssertion;
@property(strong) NSTimer *timer;
@end
@implementation KlanglaborLockDisplay
- (void)releaseAssertions {
    if (self.displayAssertion) { IOPMAssertionRelease(self.displayAssertion); self.displayAssertion = 0; }
    if (self.sleepAssertion) { IOPMAssertionRelease(self.sleepAssertion); self.sleepAssertion = 0; }
}
- (void)setLockedState:(BOOL)locked {
    if (self.locked == locked) return;
    self.locked = locked;
    if (locked) {
        IOPMAssertionID displayID = 0, sleepID = 0;
        IOReturn displayResult = IOPMAssertionCreateWithName(kIOPMAssertionTypePreventUserIdleDisplaySleep,
            kIOPMAssertionLevelOn, CFSTR("Klanglabor QR sichtbar bei gesperrtem Mac"), &displayID);
        IOReturn sleepResult = IOPMAssertionCreateWithName(kIOPMAssertionTypePreventUserIdleSystemSleep,
            kIOPMAssertionLevelOn, CFSTR("Klanglabor QR sichtbar bei gesperrtem Mac"), &sleepID);
        self.displayAssertion = displayID; self.sleepAssertion = sleepID;
        NSLog(@"Locked; display assertion=%d, sleep assertion=%d", displayResult, sleepResult);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 2*NSEC_PER_SEC), dispatch_get_main_queue(), ^{
            if (self.locked) [self showScreenSaver];
        });
    } else {
        [self releaseAssertions];
        NSLog(@"Unlocked; display and sleep assertions released");
    }
}
- (void)showScreenSaver {
    if (!self.locked) return;
    for (NSRunningApplication *app in NSWorkspace.sharedWorkspace.runningApplications) {
        if ([app.bundleIdentifier isEqualToString:@"com.apple.ScreenSaver.Engine"]) return;
    }
    NSURL *url = [NSURL fileURLWithPath:@"/System/Library/CoreServices/ScreenSaverEngine.app"];
    [NSWorkspace.sharedWorkspace openApplicationAtURL:url configuration:NSWorkspaceOpenConfiguration.configuration
        completionHandler:^(NSRunningApplication *app, NSError *error) {
            if (error) NSLog(@"ScreenSaverEngine: %@", error.localizedDescription);
            else NSLog(@"ScreenSaverEngine started");
        }];
}
- (void)onLock:(NSNotification *)note { [self setLockedState:YES]; }
- (void)onUnlock:(NSNotification *)note { [self setLockedState:NO]; }
- (void)checkSession {
    CFDictionaryRef session = CGSessionCopyCurrentDictionary();
    if (session) {
        NSDictionary *dict = CFBridgingRelease(session);
        id value = dict[@"CGSSessionScreenIsLocked"];
        if (value) [self setLockedState:[value boolValue]];
    }
    // Wait for a quiet login window so typing a password is never interrupted.
    if (self.locked && CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateCombinedSessionState,
                                                            kCGAnyInputEventType) >= 20) [self showScreenSaver];
}
- (void)start {
    NSDistributedNotificationCenter *center = NSDistributedNotificationCenter.defaultCenter;
    [center addObserver:self selector:@selector(onLock:) name:@"com.apple.screenIsLocked" object:nil
         suspensionBehavior:NSNotificationSuspensionBehaviorDeliverImmediately];
    [center addObserver:self selector:@selector(onUnlock:) name:@"com.apple.screenIsUnlocked" object:nil
         suspensionBehavior:NSNotificationSuspensionBehaviorDeliverImmediately];
    self.timer = [NSTimer scheduledTimerWithTimeInterval:10 repeats:YES block:^(NSTimer *timer) {
        [self checkSession];
    }];
    [self checkSession];
    NSLog(@"Klanglabor lock display ready");
}
@end
int main(int argc, const char *argv[]) {
    @autoreleasepool {
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyProhibited];
        KlanglaborLockDisplay *display = [KlanglaborLockDisplay new];
        [display start];
        [NSApp run];
    }
    return 0;
}
