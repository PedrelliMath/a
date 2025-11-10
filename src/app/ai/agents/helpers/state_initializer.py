from app.db.models import Channel
from app.agents.schemas.agents.graph.state import GraphState

class GraphStateInitializer:
    def __init__(
            self,
            channel: Channel
    ):
        self.channel = channel
    
    async def init_graph_state(
            self, 
            user_message: str
        ) -> GraphState:

        params = self.__get_last_message_params_or_create_new(self.channel)

        return GraphState(
            channel=self.channel,
            user_message=user_message,
            current_proficiency_level=params['current_specific_skill'],
            current_specific_skill=params['current_specific_skill'],
            current_question_set=params['current_question_set']     
        )
    
    def __get_last_message_params_or_create_new(
            self,
            channel: Channel
        ) -> dict:

        last_user_message = channel.message_history[-1]
        last_message_params = last_user_message.get("params")
        
        last_specific_skill = last_message_params.get(
            "specific_skill", 
            channel.skill.questions['skills'][0]
        )

        current_specific_skill = (  
            last_message_params
            .get("agent_details")
            .get("progress_tracker")
            .get("specific_skill")
        )

        if not current_specific_skill:
            current_specific_skill = last_specific_skill

        current_proficiency_level = last_message_params.get(
            "achieved_bloom_level", 
            "analisar"
        )
        
        current_question_set = (
            channel.skill.questions[current_specific_skill]
            [current_proficiency_level]
        )
                
        return {
            "current_specific_skill":current_specific_skill,
            "current_proficiency_level":current_proficiency_level,
            "current_question_set":current_question_set
        }


        


