export class FullscreenWidget {
    constructor() {}

    isFullScreenAsync = async (): Promise<boolean> => {
        return document.fullscreenElement != null;
    };
    setFullScreenAsync = async (enable?: boolean): Promise<void> => {
        if (enable == null) {
            enable = !(await this.isFullScreenAsync());
        }
        if (enable) {
            if (document.fullscreenElement == null && document.fullscreenEnabled) {
                await document.body.requestFullscreen();
            }
        } else {
            if (document.fullscreenElement != null) {
                await document.exitFullscreen();
            }
        }
    };
}
