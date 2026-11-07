cmake_minimum_required(VERSION 3.21)
project(veranda_qt_comparison LANGUAGES CXX)

find_package(Qt6 6.4 REQUIRED COMPONENTS Widgets)
qt_add_executable(veranda-qt-comparison main.cpp)
target_compile_features(veranda-qt-comparison PRIVATE cxx_std_17)
target_link_libraries(veranda-qt-comparison PRIVATE Qt6::Widgets)
if(MSVC)
    target_compile_options(veranda-qt-comparison PRIVATE /W4 /utf-8)
else()
    target_compile_options(veranda-qt-comparison PRIVATE -Wall -Wextra -Wpedantic)
endif()
# Keep a directly runnable executable on every platform for the comparison probe.
set_target_properties(veranda-qt-comparison PROPERTIES MACOSX_BUNDLE FALSE)
