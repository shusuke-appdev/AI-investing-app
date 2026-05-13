import asyncio
import sys

sys.path.append('.')
from frontend.state.market_state import MarketState


class MockState:
    market_type = 'US'
    error_msg = ''
    option_error_msg = ''
    is_fetching = False
    option_analysis = []
    market_signals = []
    indices_data = []
    sectors_data = []
    others_data = []
    evaluation = {}
    microstructure = None
    momentum_data = []

    _fetch_microstructure = MarketState._fetch_microstructure
    _fetch_momentum = MarketState._fetch_momentum

async def main():
    state = MockState()
    fn = MarketState.fetch_market_data.fn.__get__(state)
    gen = fn()
    try:
        while True:
            await gen.__anext__()
    except StopAsyncIteration:
        pass

    print('Error:', state.error_msg)
    print('Option error:', state.option_error_msg)
    print('Options len:', len(state.option_analysis))
    print('Signals len:', len(state.market_signals))
    print('Microstructure:', state.microstructure)

if __name__ == '__main__':
    asyncio.run(main())
