/** The trame websocket URL for a host and port, on the page's scheme. */
export function trameWebSocketUrl(host: string, port: number): string {
    const secure = window.location.protocol === 'https:';
    return `ws${secure ? 's' : ''}://${host}:${port}/ws`;
}
