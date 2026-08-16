// Brothrone 글쓰기 — 맥 네이티브 껍데기
//
// 화면(HTML)과 기능(Python 서버)은 tools/blog-editor 를 그대로 쓴다.
// 이 파일은 창을 띄우고, 서버를 자식 프로세스로 관리하는 역할만 한다.
// 빌드는 tools/make-app.sh 가 Cfg.swift 를 만들어 함께 컴파일한다.

import Cocoa
import WebKit
import UniformTypeIdentifiers

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {

    var window: NSWindow!
    var webView: WKWebView!
    var server: Process?
    var url: URL { URL(string: "http://127.0.0.1:\(Cfg.port)/")! }

    // MARK: 시작

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        buildWindow()
        NSApp.activate(ignoringOtherApps: true)

        // 블로그 폴더 접근 권한을 앱이 먼저 확인한다.
        // 폴더가 ~/Desktop 안에 있으면 macOS 가 접근 허용을 묻는데,
        // 그 관문을 자식 파이썬이 먼저 건드리면 시작 단계(getcwd)에서 멈춰 버린다.
        // 앱이 먼저 물어보게 하면 안내문과 함께 정상적으로 허용창이 뜬다.
        DispatchQueue.global().async {
            let ok = FileManager.default.isReadableFile(atPath: Cfg.repo + "/_config.yml")
            DispatchQueue.main.async {
                guard ok else {
                    self.fail("""
                        블로그 폴더를 읽을 수 없습니다.

                        \(Cfg.repo)

                        시스템 설정 → 개인정보 보호 및 보안 → 파일 및 폴더 에서
                        Editor 의 폴더 접근을 허용한 뒤 다시 열어주세요.
                        """)
                    return
                }
                self.startServerIfNeeded()
                self.waitForServerThenLoad()
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }

    /// 앱을 끄면 서버도 같이 내린다 (터미널에 유령 프로세스가 남지 않게)
    func applicationWillTerminate(_ note: Notification) {
        server?.terminate()
    }

    // MARK: 창

    func buildWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 880),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.title = "Editor"
        window.minSize = NSSize(width: 880, height: 600)
        window.center()
        window.setFrameAutosaveName("BrothroneEditorWindow")   // 위치·크기 기억

        let conf = WKWebViewConfiguration()
        conf.defaultWebpagePreferences.allowsContentJavaScript = true
        webView = WKWebView(frame: .zero, configuration: conf)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = false
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
    }

    // MARK: 서버

    /// 이미 떠 있으면(터미널에서 ./blog-editor 로 켜 둔 경우 등) 새로 띄우지 않는다.
    func startServerIfNeeded() {
        if ping() { return }

        let p = Process()
        p.executableURL = URL(fileURLWithPath: Cfg.python)
        // 절대 경로로 넘기고 작업 폴더는 건드리지 않는다.
        // 작업 폴더가 ~/Desktop 안이면 파이썬이 시작하자마자 getcwd() 에서
        // 폴더 접근 관문에 걸려 그대로 멈춰버린다. server.py 는 자기 파일 위치로
        // 블로그 폴더를 찾으므로 작업 폴더가 필요 없다.
        p.arguments = [Cfg.repo + "/tools/blog-editor/server.py", "--no-open"]
        p.currentDirectoryURL = URL(fileURLWithPath: "/")

        var env = ProcessInfo.processInfo.environment
        // Finder에서 켜면 PATH가 좁아져 magick(homebrew)을 못 찾는다
        env["PATH"] = Cfg.extraPath + ":" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        // LANG이 없으면 하위 도구들이 US-ASCII로 동작해 한글에서 깨진다
        if env["LANG"] == nil { env["LANG"] = "en_US.UTF-8" }
        if env["LC_ALL"] == nil { env["LC_ALL"] = "en_US.UTF-8" }
        p.environment = env

        let log = FileHandle(forWritingAtPath: Cfg.logPath)
            ?? { FileManager.default.createFile(atPath: Cfg.logPath, contents: nil)
                 return FileHandle(forWritingAtPath: Cfg.logPath)! }()
        log.seekToEndOfFile()
        p.standardError = log
        p.standardOutput = log

        do {
            try p.run()
            server = p
        } catch {
            fail("글쓰기 서버를 시작하지 못했습니다.\n\n\(error.localizedDescription)")
        }
    }

    func ping() -> Bool {
        var alive = false
        let sem = DispatchSemaphore(value: 0)
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(Cfg.port)/api/config")!)
        req.timeoutInterval = 0.8
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            if let h = resp as? HTTPURLResponse, h.statusCode == 200 { alive = true }
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 1.5)
        return alive
    }

    /// 서버가 뜨기 전에 열면 오류 페이지가 보이므로, 준비될 때까지 기다렸다 연다.
    ///
    /// 첫 실행에서는 macOS 폴더 접근 허용창이 떠서 사용자가 누를 때까지 서버가 멈춰 있다.
    /// 그래서 시간만으로 끊지 않고, 서버 프로세스가 살아 있는 동안은 계속 기다린다.
    func waitForServerThenLoad() {
        DispatchQueue.global().async {
            let deadline = Date().addingTimeInterval(300)   // 마지막 안전장치 5분
            while Date() < deadline {
                if self.ping() {
                    DispatchQueue.main.async { self.webView.load(URLRequest(url: self.url)) }
                    return
                }
                // 우리가 띄운 서버가 죽었다면 더 기다릴 이유가 없다
                if let s = self.server, !s.isRunning {
                    let log = (try? String(contentsOfFile: Cfg.logPath, encoding: .utf8)) ?? ""
                    DispatchQueue.main.async {
                        self.fail("글쓰기 서버가 시작하자마자 종료됐습니다.\n\n"
                            + (log.isEmpty ? "기록: \(Cfg.logPath)" : String(log.suffix(400))))
                    }
                    return
                }
                Thread.sleep(forTimeInterval: 0.4)
            }
            DispatchQueue.main.async {
                self.fail("""
                    글쓰기 서버가 응답하지 않습니다.

                    폴더 접근 허용창이 떠 있다면 '허용'을 누른 뒤 다시 열어주세요.

                    기록: \(Cfg.logPath)
                    """)
            }
        }
    }

    func fail(_ msg: String) {
        let a = NSAlert()
        a.alertStyle = .critical
        a.messageText = "Editor"
        a.informativeText = msg
        a.addButton(withTitle: "종료")
        a.runModal()
        NSApp.terminate(nil)
    }

    // MARK: 메뉴 (없으면 ⌘C/⌘V 같은 편집 단축키가 동작하지 않는다)

    func buildMenu() {
        let main = NSMenu()

        let appItem = NSMenuItem(); main.addItem(appItem)
        let app = NSMenu()
        app.addItem(withTitle: "Editor 정보",
                    action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        app.addItem(.separator())
        app.addItem(withTitle: "가리기", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        app.addItem(withTitle: "다른 항목 가리기",
                    action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "H")
        app.addItem(.separator())
        app.addItem(withTitle: "종료", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = app

        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "편집")
        edit.addItem(withTitle: "실행 취소", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "다시 실행", action: Selector(("redo:")), keyEquivalent: "Z")
        edit.addItem(.separator())
        edit.addItem(withTitle: "오려두기", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "복사", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "붙여넣기", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "전체 선택", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit

        let viewItem = NSMenuItem(); main.addItem(viewItem)
        let view = NSMenu(title: "보기")
        view.addItem(withTitle: "새로고침", action: #selector(reloadPage), keyEquivalent: "r")
        view.addItem(withTitle: "실제 크기", action: #selector(zoomReset), keyEquivalent: "0")
        view.addItem(withTitle: "확대", action: #selector(zoomIn), keyEquivalent: "+")
        view.addItem(withTitle: "축소", action: #selector(zoomOut), keyEquivalent: "-")
        viewItem.submenu = view

        let winItem = NSMenuItem(); main.addItem(winItem)
        let win = NSMenu(title: "윈도우")
        win.addItem(withTitle: "최소화", action: #selector(NSWindow.miniaturize(_:)), keyEquivalent: "m")
        win.addItem(withTitle: "닫기", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        winItem.submenu = win
        NSApp.windowsMenu = win

        NSApp.mainMenu = main
    }

    @objc func reloadPage() { webView.reload() }
    @objc func zoomReset()  { webView.pageZoom = 1.0 }
    @objc func zoomIn()     { webView.pageZoom = min(webView.pageZoom + 0.1, 2.0) }
    @objc func zoomOut()    { webView.pageZoom = max(webView.pageZoom - 0.1, 0.6) }

    // MARK: 웹뷰

    /// 앱 안에서는 우리 서버만 연다. 바깥 링크는 기본 브라우저로 넘긴다.
    func webView(_ w: WKWebView, decidePolicyFor nav: WKNavigationAction,
                 decisionHandler done: @escaping (WKNavigationActionPolicy) -> Void) {
        if let u = nav.request.url, u.host != "127.0.0.1" && u.scheme != "about" {
            NSWorkspace.shared.open(u)
            done(.cancel); return
        }
        done(.allow)
    }

    /// 파일 선택창. WKWebView 는 이 델리게이트가 없으면 <input type="file"> 클릭을
    /// 아무 반응 없이 무시한다 — 사진 버튼이 안 먹던 원인.
    func webView(_ w: WKWebView, runOpenPanelWith params: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo,
                 completionHandler done: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = params.allowsMultipleSelection
        panel.allowedContentTypes = [.image]
        panel.message = "본문에 넣을 사진을 고르세요"
        panel.prompt = "넣기"
        panel.beginSheetModal(for: window) { r in
            done(r == .OK ? panel.urls : nil)
        }
    }

    /// window.alert / confirm 을 실제 시스템 대화상자로 띄운다 (없으면 무시돼 버린다)
    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage msg: String,
                 initiatedByFrame f: WKFrameInfo, completionHandler done: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = msg; a.addButton(withTitle: "확인")
        a.beginSheetModal(for: window) { _ in done() }
    }

    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage msg: String,
                 initiatedByFrame f: WKFrameInfo, completionHandler done: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = msg
        a.addButton(withTitle: "확인"); a.addButton(withTitle: "취소")
        a.beginSheetModal(for: window) { r in done(r == .alertFirstButtonReturn) }
    }

    /// window.prompt — 이것도 없으면 무시된다 (링크 주소 입력창이 안 뜨던 원인)
    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String,
                 defaultText: String?, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping (String?) -> Void) {
        let a = NSAlert()
        a.messageText = prompt
        a.addButton(withTitle: "확인"); a.addButton(withTitle: "취소")
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
        field.stringValue = defaultText ?? ""
        a.accessoryView = field
        a.window.initialFirstResponder = field
        a.beginSheetModal(for: window) { r in
            done(r == .alertFirstButtonReturn ? field.stringValue : nil)
        }
    }
}

@main
enum Main {
    // NSApplication.delegate 는 약한 참조라, 여기서 강하게 붙들어 둔다
    static let delegate = AppDelegate()

    static func main() {
        let app = NSApplication.shared
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
