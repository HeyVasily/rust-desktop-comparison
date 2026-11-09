// Synthetic Qt Widgets UI only: no Qt Quick, WebEngine, backend, or polling.
#include <QApplication>
#include <QButtonGroup>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QVBoxLayout>
#include <QWidget>
#include <QTimer>
#include <iostream>
#include <memory>
#ifdef VERANDA_SHELL_CHECKS
#include "shell_checks.h"
#endif

static QString projectName(int project) {
    return QStringLiteral("project-%1").arg(project + 1, 3, 10, QLatin1Char('0'));
}

static QString yardName(int yard) {
    return QStringLiteral("yard-%1").arg(yard, 2, 10, QLatin1Char('0'));
}

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    QApplication::setApplicationName("Veranda Qt Widgets comparison");
#ifdef VERANDA_SHELL_CHECKS
    if (shell::handedToRunningInstance()) return 0;
#endif
    QWidget window;
    window.setWindowTitle("Veranda Qt Widgets comparison");
    window.resize(960, 640);
    auto *root = new QVBoxLayout(&window);
    root->setContentsMargins(12, 12, 12, 12);
    root->setSpacing(12);
    auto *heading = new QLabel("Veranda / Qt Widgets");
    QFont headingFont = heading->font();
    headingFont.setPointSize(18);
    headingFont.setBold(true);
    heading->setFont(headingFont);
    root->addWidget(heading);
    root->addWidget(new QLabel("Synthetic comparison · 10 yards · 100 projects · no backend"));

    int selectedYard = 0;
    int refreshes = 0;
    auto *toolbar = new QHBoxLayout;
    auto *refresh = new QPushButton("Refresh");
    auto *snapshot = new QLabel("Snapshot 0 · local fixture");
    auto *filter = new QLineEdit;
    filter->setAccessibleName("Filter projects");
    filter->setFixedWidth(240);
    toolbar->addWidget(refresh);
    toolbar->addWidget(snapshot);
    auto *filterLabel = new QLabel("&Filter:");
    filterLabel->setBuddy(filter);
    toolbar->addWidget(filterLabel);
    toolbar->addWidget(filter);
    toolbar->addStretch();
    root->addLayout(toolbar);

    auto *body = new QHBoxLayout;
    body->setSpacing(12);
    auto *yards = new QWidget;
    yards->setFixedWidth(200);
    auto *yardLayout = new QVBoxLayout(yards);
    yardLayout->setContentsMargins(0, 0, 0, 0);
    yardLayout->setSpacing(4);
    yardLayout->addWidget(new QLabel("Yards"));
    auto *yardButtons = new QButtonGroup(&window);
    for (int yard = 1; yard <= 10; ++yard) {
        auto *button = new QPushButton(yardName(yard) + "     10 projects");
        button->setMinimumHeight(38);
        button->setCheckable(true);
        yardButtons->addButton(button, yard);
        yardLayout->addWidget(button);
    }
    auto *all = new QPushButton("All projects");
    all->setCheckable(true);
    all->setChecked(true);
    yardButtons->addButton(all, 0);
    yardLayout->addWidget(all);
    yardLayout->addStretch();
    body->addWidget(yards);

    auto *projectLayout = new QVBoxLayout;
    auto *listTitle = new QLabel("All projects");
    projectLayout->addWidget(listTitle);
    projectLayout->addWidget(new QLabel("Project                                      State"));
    auto *projects = new QListWidget;
    projects->setAccessibleName("Projects");
    projects->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    for (int project = 0; project < 100; ++project) {
        auto *row = new QListWidgetItem(projectName(project) + "                 NOT_CREATED", projects);
        row->setData(Qt::UserRole, project);
        row->setSizeHint(QSize(0, 38));
    }
    projectLayout->addWidget(projects);
    body->addLayout(projectLayout, 1);
    auto *details = new QLabel;
    details->setFixedWidth(250);
    details->setAlignment(Qt::AlignLeft | Qt::AlignTop);
    details->setWordWrap(true);
    body->addWidget(details);
    root->addLayout(body, 1);

    auto updateFilter = [&] {
        for (int project = 0; project < 100; ++project) {
            projects->item(project)->setHidden(
                (selectedYard != 0 && project / 10 + 1 != selectedYard) ||
                !projectName(project).contains(filter->text(), Qt::CaseSensitive));
        }
    };
    QObject::connect(projects, &QListWidget::currentItemChanged, &window,
                     [details](QListWidgetItem *current, QListWidgetItem *) {
        if (!current) return;
        const int project = current->data(Qt::UserRole).toInt();
        details->setText("Project details\n\n" + projectName(project) + "\n" +
                         yardName(project / 10 + 1) + "\nNOT_CREATED\n\n"
                         "Synthetic data in memory.\n\nSelect a yard or project. "
                         "Edit the filter. Refresh advances the fixture snapshot.");
        std::cout << "project " << project + 1 << std::endl;
    });
    QObject::connect(yardButtons, &QButtonGroup::idClicked, &window, [&](int yard) {
        selectedYard = yard;
        listTitle->setText(yard == 0 ? "All projects" : yardName(yard));
        updateFilter();
        if (yard > 0) projects->setCurrentRow((yard - 1) * 10);
        std::cout << "yard " << yard << std::endl;
    });
    QObject::connect(filter, &QLineEdit::textChanged, &window, [&](const QString &text) {
        updateFilter();
        std::cout << "filter " << text.toStdString() << std::endl;
    });
    QObject::connect(refresh, &QPushButton::clicked, &window, [&] {
        snapshot->setText(QString("Snapshot %1 · local fixture").arg(++refreshes));
        std::cout << "refresh " << refreshes << std::endl;
    });
    projects->setCurrentRow(0);
    window.show();
    refresh->setFocus(Qt::OtherFocusReason);
    if (qEnvironmentVariableIsSet("COMPARISON_DISPLAY_DIAGNOSTICS")) {
        QTimer::singleShot(100, &window, [&window] {
            const auto platform = QGuiApplication::platformName();
            const auto backend = platform.startsWith("wayland") ? "wayland" :
                                 (platform == "xcb" ? "x11" : "unavailable");
            const auto size = window.contentsRect().size() * window.devicePixelRatioF();
            std::cout << "DISPLAY_DIAGNOSTIC {\"name\":\"qt\",\"backend\":\"" << backend
                      << "\",\"content_width\":" << size.width()
                      << ",\"content_height\":" << size.height()
                      << ",\"ready\":" << (window.isVisible() ? "true" : "false")
                      << "}" << std::endl;
        });
    }
#ifdef VERANDA_SHELL_CHECKS
    std::unique_ptr<shell::Checks> shellChecks;
    if (shell::enabled()) shellChecks = std::make_unique<shell::Checks>(&window);
#endif
    return app.exec();
}
