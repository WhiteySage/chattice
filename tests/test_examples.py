"""Executable documentation examples."""


async def test_echo_bot() -> None:
    from examples.bots.echo_bot import main

    await main()


async def test_command_bot() -> None:
    from examples.bots.command_bot import main

    await main()


async def test_buttons_bot() -> None:
    from examples.bots.buttons_bot import main

    await main()


async def test_form_bot() -> None:
    from examples.bots.form_bot import main

    await main()


async def test_dialog_bot() -> None:
    from examples.bots.dialog_bot import main

    await main()


async def test_fsm_bot() -> None:
    from examples.bots.fsm_bot import main

    await main()


async def test_fastapi_bot() -> None:
    from examples.bots.fastapi_bot import main

    await main()


async def test_pubsub_bot() -> None:
    from examples.bots.pubsub_bot import main

    await main()


async def test_workspace_events_bot() -> None:
    from examples.bots.workspace_events_bot import main

    await main()


async def test_scenario_registration_fsm() -> None:
    from examples.scenarios import registration_fsm

    await registration_fsm.main()


async def test_scenario_registration_dialog() -> None:
    from examples.scenarios import registration_dialog

    await registration_dialog.main()


async def test_scenario_request_form() -> None:
    from examples.scenarios import request_form

    await request_form.main()


async def test_scenario_request_form_plus_fsm() -> None:
    from examples.scenarios import request_form_plus_fsm

    await request_form_plus_fsm.main()


async def test_scenario_dynamic_employee_picker() -> None:
    from examples.scenarios import dynamic_employee_picker

    await dynamic_employee_picker.main()


async def test_scenario_private_dialog_to_public_card() -> None:
    from examples.scenarios import private_dialog_to_public_card

    await private_dialog_to_public_card.main()


async def test_scenario_apphome_dashboard() -> None:
    from examples.scenarios import apphome_dashboard

    await apphome_dashboard.main()


async def test_scenario_link_preview() -> None:
    from examples.scenarios import link_preview

    await link_preview.main()


async def test_scenario_text_triggers() -> None:
    from examples.scenarios import text_triggers

    await text_triggers.main()


async def test_scenario_buttons_menu() -> None:
    from examples.scenarios import buttons_menu

    await buttons_menu.main()


async def test_scenario_crm_workflow() -> None:
    from examples.production.crm_workflow.main import main

    await main()
