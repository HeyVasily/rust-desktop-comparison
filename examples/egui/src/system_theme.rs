//! Linux desktop theme integration for both native X11 and native Wayland.
//!
//! winit 0.30 does not provide `system_theme` on these backends. Read the
//! freedesktop Settings portal once, then subscribe to `SettingChanged` and
//! service-owner changes. No subprocess, GTK dependency, or periodic poll is
//! involved. The portal is a shared desktop service; this app's connection,
//! worker, and zbus resources remain in the app's measured process scope.

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use eframe::egui;
use futures_lite::{StreamExt, future};
use zbus::zvariant::OwnedValue;

const SERVICE: &str = "org.freedesktop.portal.Desktop";
const PATH: &str = "/org/freedesktop/portal/desktop";
const INTERFACE: &str = "org.freedesktop.portal.Settings";
const NAMESPACE: &str = "org.freedesktop.appearance";
const KEY: &str = "color-scheme";
const NOT_RECEIVED: u32 = u32::MAX;

type Error = Box<dyn std::error::Error + Send + Sync>;

pub struct SystemTheme {
    value: Arc<AtomicU32>,
    stop: async_channel::Sender<()>,
    worker: Option<JoinHandle<()>>,
}

impl SystemTheme {
    pub fn start(ctx: egui::Context) -> std::io::Result<Self> {
        let value = Arc::new(AtomicU32::new(NOT_RECEIVED));
        let published = Arc::clone(&value);
        let (stop, stopped) = async_channel::bounded::<()>(1);
        let worker = thread::Builder::new()
            .name("desktop-theme".into())
            .spawn(move || {
                future::block_on(future::race(
                    async {
                        if let Err(error) = watch(&published, &ctx).await {
                            // A missing/broken portal is not a fatal GUI error.
                            // Report it instead of claiming successful OS following.
                            eprintln!("system_theme portal unavailable: {error}");
                        }
                    },
                    async {
                        // Closing the channel cancels pending D-Bus I/O, so the
                        // GUI does not have to wait for another settings signal.
                        let _ = stopped.recv().await;
                    },
                ));
            })?;
        Ok(Self {
            value,
            stop,
            worker: Some(worker),
        })
    }

    pub fn apply(&self, input: &mut egui::RawInput) {
        apply_scheme(self.value.load(Ordering::Acquire), input);
    }
}

impl Drop for SystemTheme {
    fn drop(&mut self) {
        self.stop.close();
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}

fn apply_scheme(value: u32, input: &mut egui::RawInput) {
    // Keep the native backend result while the portal is unavailable/starting.
    if value != NOT_RECEIVED {
        input.system_theme = match value {
            1 => Some(egui::Theme::Dark),
            2 => Some(egui::Theme::Light),
            // Portal specification: 0 and unknown values mean no preference.
            _ => None,
        };
    }
}

fn publish(value: u32, published: &AtomicU32, ctx: &egui::Context) {
    let normalized = if value <= 2 { value } else { 0 };
    if published.swap(normalized, Ordering::AcqRel) != normalized {
        let name = match normalized {
            1 => "dark",
            2 => "light",
            _ => "no-preference",
        };
        println!("system_theme source=portal scheme={name} value={value}");
        ctx.request_repaint();
    }
}

async fn read_scheme(proxy: &zbus::Proxy<'_>) -> Result<u32, Error> {
    // ReadAll is available in both versions of the portal and avoids the legacy
    // Read method's nested-variant reply. Only query the appearance namespace.
    let all: HashMap<String, HashMap<String, OwnedValue>> =
        proxy.call("ReadAll", &(&[NAMESPACE][..],)).await?;
    let value = all
        .get(NAMESPACE)
        .and_then(|settings| settings.get(KEY))
        .ok_or("Settings portal did not expose org.freedesktop.appearance color-scheme")?;
    Ok(u32::try_from(value)?)
}

async fn refresh(proxy: &zbus::Proxy<'_>, value: &AtomicU32, ctx: &egui::Context) {
    match read_scheme(proxy).await {
        Ok(scheme) => publish(scheme, value, ctx),
        Err(error) => {
            value.store(NOT_RECEIVED, Ordering::Release);
            ctx.request_repaint();
            eprintln!("system_theme portal preference unavailable: {error}");
        }
    }
}

enum PortalEvent {
    Setting(Option<zbus::Message>),
    Owner(Option<bool>),
}

async fn watch(value: &AtomicU32, ctx: &egui::Context) -> Result<(), Error> {
    let connection = zbus::connection::Builder::session()?
        .method_timeout(Duration::from_secs(3))
        .build()
        .await?;
    let proxy = zbus::Proxy::new(&connection, SERVICE, PATH, INTERFACE).await?;

    // Subscribe before reading, so a change during the startup read is queued.
    // Filtering happens on the bus, not by waking the app for unrelated keys.
    let mut changed = proxy
        .receive_signal_with_args("SettingChanged", &[(0, NAMESPACE), (1, KEY)])
        .await?;
    let mut owners = proxy.receive_owner_changed().await?;
    refresh(&proxy, value, ctx).await;

    loop {
        let event = future::race(
            async { PortalEvent::Setting(changed.next().await) },
            async { PortalEvent::Owner(owners.next().await.map(|owner| owner.is_some())) },
        )
        .await;
        match event {
            PortalEvent::Setting(Some(message)) => {
                let body = message.body().deserialize::<(String, String, OwnedValue)>();
                match body {
                    Ok((namespace, key, setting)) if namespace == NAMESPACE && key == KEY => {
                        match u32::try_from(setting) {
                            Ok(scheme) => publish(scheme, value, ctx),
                            Err(error) => eprintln!("system_theme invalid portal value: {error}"),
                        }
                    }
                    Ok(_) => {}
                    Err(error) => eprintln!("system_theme invalid portal signal: {error}"),
                }
            }
            // Re-read on service replacement/restart; do not poll for recovery.
            PortalEvent::Owner(Some(true)) => refresh(&proxy, value, ctx).await,
            PortalEvent::Owner(Some(false)) => {
                value.store(NOT_RECEIVED, Ordering::Release);
                ctx.request_repaint();
                eprintln!("system_theme portal service disappeared; using native fallback");
            }
            PortalEvent::Setting(None) | PortalEvent::Owner(None) => {
                value.store(NOT_RECEIVED, Ordering::Release);
                ctx.request_repaint();
                return Err("Settings portal connection closed".into());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn portal_dark_and_light_map_to_egui_system_input() {
        let mut input = egui::RawInput::default();
        apply_scheme(1, &mut input);
        assert_eq!(input.system_theme, Some(egui::Theme::Dark));
        apply_scheme(2, &mut input);
        assert_eq!(input.system_theme, Some(egui::Theme::Light));
    }

    #[test]
    fn absent_portal_preserves_native_input() {
        let mut input = egui::RawInput {
            system_theme: Some(egui::Theme::Dark),
            ..Default::default()
        };
        apply_scheme(NOT_RECEIVED, &mut input);
        assert_eq!(input.system_theme, Some(egui::Theme::Dark));
    }

    #[test]
    fn no_preference_and_unknown_values_clear_a_previous_preference() {
        for value in [0, 3, 1234] {
            let mut input = egui::RawInput {
                system_theme: Some(egui::Theme::Dark),
                ..Default::default()
            };
            apply_scheme(value, &mut input);
            assert_eq!(input.system_theme, None);
        }
    }

    struct PortalFixture(Arc<AtomicU32>);

    #[zbus::interface(name = "org.freedesktop.portal.Settings")]
    impl PortalFixture {
        fn read_all(
            &self,
            namespaces: Vec<String>,
        ) -> HashMap<String, HashMap<String, OwnedValue>> {
            assert_eq!(namespaces, [NAMESPACE]);
            HashMap::from([(
                NAMESPACE.into(),
                HashMap::from([(KEY.into(), OwnedValue::from(self.0.load(Ordering::Acquire)))]),
            )])
        }
    }

    fn wait_for_scheme(monitor: &SystemTheme, expected: u32) {
        let deadline = Instant::now() + Duration::from_secs(3);
        while monitor.value.load(Ordering::Acquire) != expected {
            assert!(
                Instant::now() < deadline,
                "portal did not deliver scheme {expected}"
            );
            thread::sleep(Duration::from_millis(10));
        }
    }

    // This checks the actual D-Bus wire protocol and listener lifecycle, not a
    // real desktop backend or screenshot. Run on a private disposable bus:
    // dbus-run-session -- env COMPARISON_TEST_ISOLATED_DBUS=1 cargo test \
    //   --manifest-path examples/egui/Cargo.toml portal_round_trip -- --ignored
    #[test]
    #[ignore = "requires an isolated dbus-run-session (never the user's desktop bus)"]
    fn portal_round_trip_and_service_restart() {
        assert_eq!(
            std::env::var("COMPARISON_TEST_ISOLATED_DBUS").as_deref(),
            Ok("1")
        );
        let scheme = Arc::new(AtomicU32::new(1));
        let server = future::block_on(async {
            zbus::connection::Builder::session()
                .unwrap()
                .name(SERVICE)
                .unwrap()
                .serve_at(PATH, PortalFixture(Arc::clone(&scheme)))
                .unwrap()
                .build()
                .await
                .unwrap()
        });
        let monitor = SystemTheme::start(egui::Context::default()).unwrap();
        wait_for_scheme(&monitor, 1);

        for (next, normalized) in [(2_u32, 2), (0, 0), (1, 1), (42, 0)] {
            scheme.store(next, Ordering::Release);
            future::block_on(server.emit_signal(
                None::<&str>,
                PATH,
                INTERFACE,
                "SettingChanged",
                &(NAMESPACE, KEY, OwnedValue::from(next)),
            ))
            .unwrap();
            wait_for_scheme(&monitor, normalized);
        }

        future::block_on(server.release_name(SERVICE)).unwrap();
        wait_for_scheme(&monitor, NOT_RECEIVED);
        scheme.store(2, Ordering::Release);
        future::block_on(server.request_name(SERVICE)).unwrap();
        wait_for_scheme(&monitor, 2);

        let before = Instant::now();
        drop(monitor);
        assert!(
            before.elapsed() < Duration::from_secs(3),
            "listener did not cancel promptly"
        );
    }
}
