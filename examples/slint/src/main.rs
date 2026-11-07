//! Synthetic UI only: stock Slint, in-memory data, no backend or polling.
use slint::{ComponentHandle, ModelRc, SharedString, VecModel};

slint::include_modules!();

fn project_name(project: i32) -> String {
    format!("project-{:03}", project + 1)
}

fn select_project(ui: &Demo, project: i32) {
    ui.set_selected_project(project);
    ui.set_project_name(project_name(project).into());
    ui.set_project_yard(format!("yard-{:02}", project / 10 + 1).into());
}

fn update_projects(ui: &Demo) {
    let yard = ui.get_selected_yard();
    let filter = ui.get_filter();
    let rows: Vec<ProjectRow> = (0..100)
        .filter(|project| {
            (yard == 0 || project / 10 + 1 == yard)
                && project_name(*project).contains(filter.as_str())
        })
        .map(|project| ProjectRow {
            id: project,
            name: project_name(project).into(),
        })
        .collect();
    ui.set_projects(ModelRc::new(VecModel::from(rows)));
    ui.set_list_title(if yard == 0 {
        "All projects".into()
    } else {
        format!("yard-{yard:02}").into()
    });
}

fn main() -> Result<(), slint::PlatformError> {
    // Fix the renderer across platforms; no patched Slint or Qt backend.
    slint::BackendSelector::new()
        .backend_name("winit".into())
        .renderer_name("software".into())
        .select()?;
    let ui = Demo::new()?;
    let yards: Vec<SharedString> = (1..=10)
        .map(|yard| format!("yard-{yard:02}     10 projects").into())
        .collect();
    ui.set_yards(ModelRc::new(VecModel::from(yards)));
    select_project(&ui, 0);
    update_projects(&ui);

    let weak = ui.as_weak();
    ui.on_choose_yard(move |yard| {
        let ui = weak.unwrap();
        ui.set_selected_yard(yard);
        if yard > 0 {
            select_project(&ui, (yard - 1) * 10);
        }
        update_projects(&ui);
        println!("yard {yard}");
    });
    let weak = ui.as_weak();
    ui.on_choose_project(move |project| {
        select_project(&weak.unwrap(), project);
        println!("project {}", project + 1);
    });
    let weak = ui.as_weak();
    ui.on_filter_changed(move |filter| {
        let ui = weak.unwrap();
        ui.set_filter(filter.clone());
        update_projects(&ui);
        println!("filter {filter}");
    });
    let weak = ui.as_weak();
    ui.on_refresh(move || {
        let ui = weak.unwrap();
        ui.set_snapshot(ui.get_snapshot() + 1);
        println!("refresh {}", ui.get_snapshot());
    });
    #[cfg(target_os = "windows")]
    {
        // Place the entire client on the hosted desktop before the first paint.
        // Winit stores this in its creation attributes while the window is lazy.
        ui.window().set_position(slint::PhysicalPosition::new(8, 8));
        let weak = ui.as_weak();
        // One startup observation after native creation, not an idle timer.
        slint::Timer::single_shot(std::time::Duration::from_millis(100), move || {
            if let Some(ui) = weak.upgrade() {
                let window = ui.window();
                let position = window.position();
                let size = window.size();
                println!(
                    "geometry requested_outer_position=8,8 outer_position={},{} inner_physical={}x{} scale_factor={}",
                    position.x,
                    position.y,
                    size.width,
                    size.height,
                    window.scale_factor()
                );
            }
        });
    }
    ui.run()
}
