//! Matched synthetic GTK4 desktop example written with gtk4-rs.
//! The default profile includes libadwaita's system-appearance integration.
//! No backend, filesystem inventory or production actions are simulated.

use std::cell::Cell;
use std::rc::Rc;

use gtk::prelude::*;
use gtk::{
    Application, ApplicationWindow, Box as GtkBox, Button, Entry, Label, ListBox, ListBoxRow,
    Orientation, ScrolledWindow, glib,
};

const APP_ID: &str = "org.subyard.Comparison";

#[cfg(feature = "shell-checks")]
mod shell;

fn project_of(row: &ListBoxRow) -> usize {
    usize::try_from(row.index()).expect("rows are appended in project order")
}

fn details_text(project: usize) -> String {
    format!(
        "Project details\n\nproject-{:03}\nyard-{:02}\nNOT_CREATED\n\nSynthetic data in memory.",
        project + 1,
        project / 10 + 1
    )
}

fn build_ui(app: &Application) {
    #[cfg(feature = "shell-checks")]
    if shell::forwarded_activation(app) {
        return;
    }
    let selected_yard = Rc::new(Cell::new(0usize));
    let refreshes = Rc::new(Cell::new(0u32));

    let window = ApplicationWindow::builder()
        .application(app)
        .title("Veranda GTK comparison")
        .default_width(960)
        .default_height(640)
        .build();

    let root = GtkBox::new(Orientation::Vertical, 12);
    root.set_margin_start(12);
    root.set_margin_end(12);
    root.set_margin_top(12);
    root.set_margin_bottom(12);
    window.set_child(Some(&root));
    root.append(&Label::new(Some(
        "Veranda / GTK4 — Synthetic comparison · 10 yards · 100 projects · no backend",
    )));

    let toolbar = GtkBox::new(Orientation::Horizontal, 12);
    let refresh_button = Button::with_label("Refresh");
    let snapshot = Label::new(Some("Snapshot 0 · local fixture"));
    let filter = Entry::new();
    filter.set_size_request(240, -1);
    toolbar.append(&refresh_button);
    toolbar.append(&snapshot);
    toolbar.append(&Label::new(Some("Filter:")));
    toolbar.append(&filter);
    root.append(&toolbar);

    // A normal desktop accelerator, also used by the external clipboard probe.
    let focus_filter = gtk::gio::SimpleAction::new("focus-filter", None);
    let weak_filter = filter.downgrade();
    focus_filter.connect_activate(move |_, _| {
        if let Some(entry) = weak_filter.upgrade() {
            entry.grab_focus();
            entry.select_region(0, -1);
        }
    });
    window.add_action(&focus_filter);
    app.set_accels_for_action("win.focus-filter", &["<Primary>f"]);

    {
        let refreshes = refreshes.clone();
        refresh_button.connect_clicked(move |_| {
            refreshes.set(refreshes.get() + 1);
            snapshot.set_text(&format!("Snapshot {} · local fixture", refreshes.get()));
            println!("refresh {}", refreshes.get());
        });
    }

    let body = GtkBox::new(Orientation::Horizontal, 12);
    body.set_vexpand(true);
    root.append(&body);

    let yards = GtkBox::new(Orientation::Vertical, 4);
    yards.set_size_request(200, -1);
    yards.append(&Label::new(Some("Yards")));
    body.append(&yards);

    let projects = ListBox::new();
    {
        let selected_yard = selected_yard.clone();
        let filter = filter.clone();
        projects.set_filter_func(move |row| {
            let project = project_of(row);
            let name = format!("project-{:03}", project + 1);
            let yard = selected_yard.get();
            (yard == 0 || project / 10 + 1 == yard) && name.contains(filter.text().as_str())
        });
    }
    for project in 0..100 {
        let row = ListBoxRow::new();
        row.set_size_request(-1, 38);
        row.set_child(Some(&Label::new(Some(&format!(
            "project-{:03}                 NOT_CREATED",
            project + 1
        )))));
        projects.append(&row);
    }

    let choose_yard = {
        let projects = projects.clone();
        let selected_yard = selected_yard.clone();
        move |yard: usize| {
            selected_yard.set(yard);
            projects.invalidate_filter();
            let first = if yard == 0 { 0 } else { (yard - 1) * 10 };
            let row = projects.row_at_index(i32::try_from(first).expect("small index"));
            projects.select_row(row.as_ref());
            println!("yard {yard}");
        }
    };
    for yard in 1..=10 {
        let button = Button::with_label(&format!("yard-{yard:02}     10 projects"));
        button.set_size_request(-1, 38);
        let choose_yard = choose_yard.clone();
        button.connect_clicked(move |_| choose_yard(yard));
        yards.append(&button);
    }
    let all_projects = Button::with_label("All projects");
    all_projects.connect_clicked(move |_| choose_yard(0));
    yards.append(&all_projects);

    let scroll = ScrolledWindow::new();
    scroll.set_hexpand(true);
    scroll.set_child(Some(&projects));
    body.append(&scroll);

    let details = Label::new(Some(""));
    details.set_xalign(0.0);
    details.set_yalign(0.0);
    details.set_size_request(250, -1);
    body.append(&details);

    projects.connect_row_selected(move |_, row| {
        if let Some(row) = row {
            let project = project_of(row);
            details.set_text(&details_text(project));
            println!("project {}", project + 1);
        }
    });
    {
        let projects = projects.clone();
        filter.connect_changed(move |entry| {
            projects.invalidate_filter();
            println!("filter {}", entry.text());
        });
    }

    projects.select_row(projects.row_at_index(0).as_ref());
    GtkWindowExt::set_focus(&window, Some(&refresh_button));
    window.present();
    #[cfg(feature = "shell-checks")]
    {
        // Keep the tray and hotkey alive as long as the window.
        let shell = shell::start(&window);
        window.connect_destroy(move |_| {
            let _ = &shell;
        });
    }
}

fn main() -> glib::ExitCode {
    let app = Application::builder().application_id(APP_ID).build();
    #[cfg(feature = "desktop")]
    app.connect_startup(|_| {
        adw::init().expect("initialize libadwaita desktop integration");
        let style = adw::StyleManager::default();
        // Follow the desktop preference, including changes while the app runs.
        // No GTK_THEME override, forced dark palette or polling timer is used.
        style.set_color_scheme(adw::ColorScheme::Default);
        println!("desktop_profile gtk4+libadwaita system_theme=true clipboard=gtk");
        println!("theme source=libadwaita dark={}", style.is_dark());
        style.connect_dark_notify(|style| {
            println!("theme source=libadwaita dark={}", style.is_dark());
        });
    });
    app.connect_activate(build_ui);
    app.run()
}
