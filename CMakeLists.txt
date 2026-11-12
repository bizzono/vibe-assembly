cmake_minimum_required(VERSION 3.16)
project(vibeasm VERSION 0.1.0 LANGUAGES C ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Determine vibe-assembly target name (<isa>-<os>)
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" VIBEASM_PROC)
if(VIBEASM_PROC MATCHES "^(arm64|aarch64)$")
    set(VIBEASM_ISA "arm64")
elseif(VIBEASM_PROC MATCHES "^(x86_64|amd64)$")
    set(VIBEASM_ISA "x86_64")
else()
    set(VIBEASM_ISA "${VIBEASM_PROC}")
endif()

string(TOLOWER "${CMAKE_SYSTEM_NAME}" VIBEASM_OS)
set(VIBEASM_TARGET "${VIBEASM_ISA}-${VIBEASM_OS}")
message(STATUS "vibe-assembly target: ${VIBEASM_TARGET}")

set(VIBEASM_TASKS
    base64_encode
    crc32
    mandelbrot
    nqueens
    utf8_validate
    wordcount
)

set(VIBEASM_SOURCES "")
foreach(task IN LISTS VIBEASM_TASKS)
    set(asm_path "${CMAKE_CURRENT_SOURCE_DIR}/solutions/${VIBEASM_TARGET}/${task}.s")
    set(ref_path "${CMAKE_CURRENT_SOURCE_DIR}/tasks/${task}/ref.c")
    if(EXISTS "${asm_path}")
        list(APPEND VIBEASM_SOURCES "${asm_path}")
    else()
        list(APPEND VIBEASM_SOURCES "${ref_path}")
    endif()
endforeach()

# Static library
add_library(vibeasm_static STATIC ${VIBEASM_SOURCES})
set_target_properties(vibeasm_static PROPERTIES OUTPUT_NAME vibeasm)
target_include_directories(vibeasm_static PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

# Shared library
add_library(vibeasm_shared SHARED ${VIBEASM_SOURCES})
set_target_properties(vibeasm_shared PROPERTIES OUTPUT_NAME vibeasm VERSION ${PROJECT_VERSION} SOVERSION 0)
target_include_directories(vibeasm_shared PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

add_library(vibeasm::vibeasm ALIAS vibeasm_static)

# Example CLI binary
option(VIBEASM_BUILD_EXAMPLES "Build vibe-assembly example executables" ON)
if(VIBEASM_BUILD_EXAMPLES)
    add_executable(vibe-demo examples/fast_cli.c)
    target_link_libraries(vibe-demo PRIVATE vibeasm_static)
endif()

# CTest integration
include(CTest)
if(BUILD_TESTING)
    add_test(NAME vibe-demo-smoke COMMAND vibe-demo)
endif()

# Install rules
include(GNUInstallDirs)
install(TARGETS vibeasm_static vibeasm_shared
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(FILES include/vibeasm.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
