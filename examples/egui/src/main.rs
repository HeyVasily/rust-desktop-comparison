//! Synthetic UI comparison only: no RPC, filesystem inventory or production actions.
use eframe::egui;
#[cfg(not(target_os = "windows"))]
use eframe::glow::HasContext;

#[cfg(target_os = "linux")]
include!("../../linux_display_diagnostics.rs");
#[cfg(feature = "shell-checks")]
mod shell;
#[cfg(all(target_os = "linux", feature = "desktop"))]
mod system_theme;

struct Demo {
    #[cfg(feature = "shell-checks")]
    _shell: Option<shell::Shell>,
    #[cfg(target_os = "linux")]
    reported_display: bool,
    #[cfg(all(target_os = "linux", feature = "desktop"))]
    system_theme: Option<system_theme::SystemTheme>,
    yard: usize,
    project: usize,
    filter: String,
    refreshes: usize,
}

impl Default for Demo {
    fn default() -> Self {
        Self {
            #[cfg(feature = "shell-checks")]
            _shell: None,
            #[cfg(target_os = "linux")]
            reported_display: false,
            #[cfg(all(target_os = "linux", feature = "desktop"))]
            system_theme: None,
            yard: 0,
            project: 0,
            filter: String::new(),
            refreshes: 0,
        }
    }
}

impl eframe::App for Demo {
    fn raw_input_hook(&mut self, _ctx: &egui::Context, input: &mut egui::RawInput) {
        #[cfg(all(target_os = "linux", feature = "desktop"))]
        if let Some(theme) = &self.system_theme {
            theme.apply(input);
        }
        #[cfg(not(all(target_os = "linux", feature = "desktop")))]
        let _ = input;
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let focus_filter =
            ui.input_mut(|input| input.consume_key(egui::Modifiers::COMMAND, egui::Key::F));
        #[cfg(target_os = "linux")]
        if !self.reported_display && std::env::var_os("COMPARISON_DISPLAY_DIAGNOSTICS").is_some() {
            let size = ui.max_rect().size() * ui.ctx().pixels_per_point();
            report_display("egui", _frame, size.x.round() as u32, size.y.round() as u32);
            self.reported_display = true;
        }
        egui::Panel::top("header").exact_size(100.0).show(ui, |ui| {
            ui.add_space(12.0);
            ui.heading("Veranda / egui");
            ui.label("Synthetic comparison · 10 yards · 100 projects · no backend");
            ui.horizontal(|ui| {
                if ui.button("Refresh").clicked() {
                    self.refreshes += 1;
                    println!("refresh {}", self.refreshes);
                }
                ui.label(format!("Snapshot {} · local fixture", self.refreshes));
                ui.label("Filter:");
                let filter = ui.add(
                    egui::TextEdit::singleline(&mut self.filter)
                        .id(egui::Id::unique("project-filter"))
                        .desired_width(240.0),
                );
                if focus_filter {
                    filter.request_focus();
                }
                if filter.changed() {
                    println!("filter {:?}", self.filter);
                }
            });
        });
        egui::Panel::left("yards")
            .exact_size(210.0)
            .resizable(false)
            .show(ui, |ui| {
                ui.add_space(12.0);
                ui.heading("Yards");
                for yard in 0..10 {
                    if ui
                        .add_sized(
                            [190.0, 38.0],
                            egui::Button::selectable(
                                self.yard == yard + 1,
                                format!("yard-{:02}     10 projects", yard + 1),
                            ),
                        )
                        .clicked()
                    {
                        self.yard = yard + 1;
                        self.project = yard * 10;
                        println!("yard {}", self.yard);
                    }
                }
                if ui.button("All projects").clicked() {
                    self.yard = 0;
                    println!("yard 0");
                }
            });
        egui::Panel::right("details").exact_size(250.0).resizable(false).show(ui, |ui| {
            ui.add_space(12.0);
            ui.heading("Project details");
            ui.separator();
            ui.label(format!("project-{:03}", self.project + 1));
            ui.label(format!("yard-{:02}", self.project / 10 + 1));
            ui.label("NOT_CREATED");
            ui.add_space(16.0);
            ui.label("Synthetic data in memory.");
            ui.label("Select a yard or project. Edit the filter. Refresh advances the fixture snapshot.");
        });
        egui::CentralPanel::default().show(ui, |ui| {
            ui.heading(if self.yard == 0 {
                "All projects".to_owned()
            } else {
                format!("yard-{:02}", self.yard)
            });
            ui.label("Project                                      State");
            ui.separator();
            egui::ScrollArea::vertical().show(ui, |ui| {
                for project in 0..100 {
                    let name = format!("project-{:03}", project + 1);
                    if (self.yard == 0 || project / 10 + 1 == self.yard)
                        && name.contains(&self.filter)
                    {
                        if ui
                            .add_sized(
                                [ui.available_width(), 38.0],
                                egui::Button::selectable(
                                    self.project == project,
                                    format!("{name}                 NOT_CREATED"),
                                ),
                            )
                            .clicked()
                        {
                            self.project = project;
                            println!("project {}", self.project + 1);
                        }
                    }
                }
            });
        });
    }
}

fn main() -> eframe::Result {
    println!(
        "desktop_profile={} clipboard={} links={} system_fonts={}",
        if cfg!(feature = "desktop") {
            "desktop"
        } else {
            "diagnostic-core"
        },
        if cfg!(feature = "desktop") {
            "os"
        } else {
            "internal-only"
        },
        cfg!(feature = "desktop"),
        cfg!(feature = "desktop"),
    );
    #[cfg(feature = "shell-checks")]
    let _instance = shell::single_instance();
    #[cfg(target_os = "windows")]
    let options = {
        // Hosted Windows desktops expose OpenGL 1.1. DX12 supports their WARP
        // software adapter and uses hardware when available; report the selection.
        let mut setup = eframe::egui_wgpu::WgpuSetupCreateNew::without_display_handle();
        setup.instance_descriptor.backends = eframe::wgpu::Backends::DX12;
        // Use Windows' built-in shader compiler, avoiding an untracked DXC DLL.
        setup
            .instance_descriptor
            .backend_options
            .dx12
            .shader_compiler = eframe::wgpu::Dx12Compiler::Fxc;
        eframe::NativeOptions {
            viewport: egui::ViewportBuilder::default().with_inner_size([960.0, 640.0]),
            renderer: eframe::Renderer::Wgpu,
            wgpu_options: eframe::WgpuConfiguration {
                wgpu_setup: setup.into(),
                ..Default::default()
            },
            ..Default::default()
        }
    };
    #[cfg(not(target_os = "windows"))]
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default().with_inner_size([960.0, 640.0]),
        renderer: eframe::Renderer::Glow,
        ..Default::default()
    };
    eframe::run_native(
        "Veranda egui comparison",
        options,
        Box::new(|cc| {
            #[cfg(target_os = "windows")]
            if let Some(render_state) = &cc.wgpu_render_state {
                let info = render_state.adapter.get_info();
                println!(
                    "renderer wgpu backend={:?} adapter={:?} device_type={:?} driver={:?} driver_info={:?} shader_compiler=Fxc",
                    info.backend, info.name, info.device_type, info.driver, info.driver_info
                );
            }
            #[cfg(not(target_os = "windows"))]
            if let Some(gl) = &cc.gl {
                // The creation callback owns a current OpenGL context.
                println!("renderer {}", unsafe {
                    gl.get_parameter_string(eframe::glow::RENDERER)
                });
            }
            // Follow the OS light/dark preference (egui's default ThemePreference::System);
            // when the OS reports none, use light instead of egui's dark fallback.
            cc.egui_ctx
                .options_mut(|options| options.fallback_theme = egui::Theme::Light);
            cc.egui_ctx.set_theme(egui::ThemePreference::System);
            #[cfg(all(target_os = "linux", feature = "desktop"))]
            let system_theme = match system_theme::SystemTheme::start(cc.egui_ctx.clone()) {
                Ok(theme) => Some(theme),
                Err(error) => {
                    eprintln!("system_theme portal worker unavailable: {error}");
                    None
                }
            };
            #[cfg(feature = "shell-checks")]
            return Ok(Box::new(Demo {
                _shell: shell::start(&cc.egui_ctx),
                #[cfg(all(target_os = "linux", feature = "desktop"))]
                system_theme,
                ..Demo::default()
            }));
            #[cfg(not(feature = "shell-checks"))]
            Ok(Box::new(Demo {
                #[cfg(all(target_os = "linux", feature = "desktop"))]
                system_theme,
                ..Demo::default()
            }))
        }),
    )
}
