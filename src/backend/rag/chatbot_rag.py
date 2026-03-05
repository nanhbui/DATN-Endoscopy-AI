import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# LangChain and LangGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

# Tavily search
from langchain_community.tools.tavily_search import TavilySearchResults

# LangSmith tracing
from langsmith import Client
from langsmith.run_helpers import traceable

# Pydantic models
from pydantic_models import (
    AgentState,
    TopicClassificationResult,
    ScopeClassification,
    RetrievalResult,
    ToolCallResult
)

# Data processor
from data_processor import DataProcessor

# Load environment variables
load_dotenv()

# Initialize LangSmith if API key is available
LANGSMITH_API_KEY = os.getenv("LANGCHAIN_API_KEY")
if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "product-rag-chatbot")
    print(f"[INFO] LangSmith tracing enabled for project: {os.environ['LANGCHAIN_PROJECT']}")
else:
    print("[INFO] LangSmith tracing disabled (no LANGCHAIN_API_KEY)")
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


class ProductRAGChatbot:
    """
    RAG-powered chatbot with LangGraph workflow for product queries.

    This chatbot uses a state machine to:
    1. Classify user queries (in-scope vs out-of-scope)
    2. Retrieve relevant product information from vector database
    3. Optionally search external sources (Tavily)
    4. Generate contextual responses using OpenAI
    """

    def __init__(
        self,
        data_processor: DataProcessor,
        product_context: str = "Product X",
        model_name: str = None,
        temperature: float = 0.7
    ):
        """
        Initialize the RAG chatbot.

        Args:
            data_processor: DataProcessor instance with vector store
            product_context: Context description for scope control
            model_name: OpenAI model name (default from env)
            temperature: LLM temperature (0.0 to 1.0)
        """
        self.data_processor = data_processor
        self.product_context = product_context

        # Initialize OpenAI LLM
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # Get vector store
        self.vector_store = self.data_processor.get_vector_store()
        if self.vector_store is None:
            print("[WARNING] Vector store not available. Initializing...")
            self.data_processor.initialize_vector_store()
            self.vector_store = self.data_processor.get_vector_store()

        # Initialize Tavily search (optional)
        self.tavily_search = None
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if tavily_api_key:
            try:
                self.tavily_search = TavilySearchResults(
                    api_key=tavily_api_key,
                    max_results=3
                )
                print("[INFO] Tavily search initialized")
            except Exception as e:
                print(f"[WARNING] Tavily search not available: {e}")

        # Build LangGraph workflow
        self.workflow = self._build_workflow()

        print(f"[INFO] ProductRAGChatbot initialized with model: {self.model_name}")

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph state machine workflow.

        Workflow nodes:
        - topic_classification: Classify query scope
        - retrieval_and_tools: Perform RAG lookup and optional Tavily search
        - generation: Generate final response

        Returns:
            Compiled StateGraph workflow
        """
        # Create state graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("topic_classification", self._topic_classification_node)
        workflow.add_node("retrieval_and_tools", self._retrieval_and_tools_node)
        workflow.add_node("generation", self._generation_node)

        # Set entry point
        workflow.set_entry_point("topic_classification")

        # Add conditional edges
        workflow.add_conditional_edges(
            "topic_classification",
            self._should_continue_after_classification,
            {
                "continue": "retrieval_and_tools",
                "end": END
            }
        )

        workflow.add_edge("retrieval_and_tools", "generation")
        workflow.add_edge("generation", END)

        # Compile workflow
        compiled_workflow = workflow.compile()

        print("[INFO] LangGraph workflow built successfully")

        return compiled_workflow

    def _topic_classification_node(self, state: AgentState) -> AgentState:
        """
        Node A: Topic Classification (Scope Control)

        This node uses OpenAI to determine if the user query is relevant
        to the product domain or out-of-scope.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with classification result
        """
        print("[NODE] Topic Classification...")

        user_query = state.user_query

        # Create classification prompt
        classification_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a scope classifier for a product information chatbot that has captured and stored specific products.

Product Context: {product_context}

The database contains captured products with detailed information. Your task is to classify if the query relates to products/database.

**CLASSIFICATION RULES:**
1. **IN_SCOPE** - Questions about:
   - ANY product mentioned (phone case, vase, electronics, etc.) - likely refers to captured products
   - Product features, usage, description, characteristics  
   - Database content, captured data, system information
   - Shopping/purchasing queries, finding similar products
   - Web search for products or comparisons

2. **OUT_OF_SCOPE** - Only for:
   - Weather, politics, personal information
   - Completely unrelated topics

**CRITICAL:** If user mentions any product type (like "phone case"), assume it refers to captured data and classify as IN_SCOPE.

**EXAMPLES:**
- "What is phone case, tell me usage" → IN_SCOPE (asking about captured phone case product)
- "Describe this product" → IN_SCOPE 
- "What's the weather?" → OUT_OF_SCOPE

IMPORTANT: Be very permissive for any product-related queries.

Respond ONLY in the required JSON format:
{{
    "classification": "in_scope" or "out_of_scope",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation based on the query and product context"
}}"""),
            ("human", "{query}")
        ])

        # Call LLM for classification
        messages = classification_prompt.format_messages(
            product_context=self.product_context,
            query=user_query
        )

        try:
            response = self.llm.invoke(messages)
            response_text = response.content

            # Parse JSON response
            import json
            classification_data = json.loads(response_text)

            is_in_scope = classification_data.get("classification") == "in_scope"

            classification_result = TopicClassificationResult(
                classification=ScopeClassification.IN_SCOPE if is_in_scope else ScopeClassification.OUT_OF_SCOPE,
                is_in_scope=is_in_scope,
                confidence=classification_data.get("confidence", 0.5),
                reason=classification_data.get("reason", ""),
                suggested_response=(
                    None if is_in_scope
                    else "I'm sorry, but I can only answer questions about our product. "
                         "Your question seems to be about something else. "
                         "Please ask me about product features, specifications, or usage."
                )
            )

            state.topic_classification = classification_result

            print(f"[CLASSIFICATION] {classification_result.classification.value} "
                  f"(confidence: {classification_result.confidence:.2f})")
            print(f"[REASON] {classification_result.reason}")

        except Exception as e:
            print(f"[ERROR] Classification failed: {e}")
            # Default to out-of-scope on error
            state.topic_classification = TopicClassificationResult(
                classification=ScopeClassification.OUT_OF_SCOPE,
                is_in_scope=False,
                confidence=0.0,
                reason=f"Classification error: {e}",
                suggested_response="I'm having trouble understanding your question. Please try rephrasing."
            )

        return state

    def _should_continue_after_classification(self, state: AgentState) -> str:
        """
        Conditional edge: Determine if workflow should continue after classification.

        Args:
            state: Current agent state

        Returns:
            "continue" if in-scope, "end" if out-of-scope
        """
        if state.topic_classification and state.topic_classification.is_in_scope:
            return "continue"
        else:
            # Set final response for out-of-scope queries
            state.final_response = (
                state.topic_classification.suggested_response
                if state.topic_classification else
                "I can only answer questions about our product."
            )
            state.workflow_complete = True
            return "end"

    def _should_use_tavily_search(self, user_query: str, rag_results: List[RetrievalResult]) -> bool:
        """
        Determine if Tavily search should be used based on query content and RAG quality
        
        Args:
            user_query: User's query string
            rag_results: Results from RAG search
            
        Returns:
            True if Tavily search should be triggered
        """
        query_lower = user_query.lower()
        
        # Keywords that indicate need for external search
        external_keywords = [
            'online', 'buy', 'purchase', 'shop', 'store', 'website', 'link',
            'similar', 'alternative', 'where to find', 'price', 'cost',
            'amazon', 'ebay', 'website', 'url', 'shopping', 'similar products'
        ]
        
        # Check if query contains external search keywords
        has_external_intent = any(keyword in query_lower for keyword in external_keywords)
        
        if has_external_intent:
            print(f"[DECISION] Triggering Tavily search due to external intent keywords")
            return True
            
        # Check RAG result quality
        if rag_results:
            avg_score = sum(r.similarity_score for r in rag_results) / len(rag_results)
            if avg_score < 0.5:  # Low similarity threshold
                print(f"[DECISION] Triggering Tavily search due to low RAG quality: {avg_score:.3f}")
                return True
        else:
            print(f"[DECISION] Triggering Tavily search due to no RAG results")
            return True
            
        print(f"[DECISION] Using RAG only - sufficient quality results")
        return False

    def _retrieval_and_tools_node(self, state: AgentState) -> AgentState:
        """
        Node B: Retrieval & Tool Calling

        This node performs:
        1. Mandatory RAG lookup against ChromaDB
        2. Optional Tavily external search if RAG results are insufficient

        Args:
            state: Current agent state

        Returns:
            Updated agent state with retrieval results
        """
        print("[NODE] Retrieval and Tools...")

        user_query = state.user_query

        # Step 1: Mandatory RAG Retrieval
        print("[TOOL] Performing RAG lookup...")
        try:
            if self.vector_store:
                # Perform similarity search
                search_results = self.vector_store.similarity_search_with_score(
                    user_query,
                    k=3  # Top 3 results
                )

                rag_results = []
                for doc, score in search_results:
                    retrieval_result = RetrievalResult(
                        document_text=doc.page_content,
                        metadata=doc.metadata,
                        similarity_score=float(score)
                    )
                    rag_results.append(retrieval_result)

                state.rag_results = rag_results

                # Log RAG results
                print(f"[RAG] Retrieved {len(rag_results)} documents")
                for i, result in enumerate(rag_results, 1):
                    print(f"  [{i}] Score: {result.similarity_score:.3f} - "
                          f"Session: {result.metadata.get('session_id', 'N/A')}")

                # Record tool call
                state.tool_calls.append(ToolCallResult(
                    tool_name="RAG Retrieval",
                    success=True,
                    result={"num_results": len(rag_results)},
                    error=None
                ))

            else:
                print("[WARNING] Vector store not available")
                state.tool_calls.append(ToolCallResult(
                    tool_name="RAG Retrieval",
                    success=False,
                    result=None,
                    error="Vector store not available"
                ))

        except Exception as e:
            print(f"[ERROR] RAG retrieval failed: {e}")
            state.tool_calls.append(ToolCallResult(
                tool_name="RAG Retrieval",
                success=False,
                result=None,
                error=str(e)
            ))

        # Step 2: Determine if external search is needed
        # Trigger Tavily for shopping, similarity, or external queries
        needs_external = self._should_use_tavily_search(user_query, state.rag_results)

        # Step 3: Optional Tavily External Search
        if needs_external and self.tavily_search:
            print("[TOOL] Performing Tavily external search...")
            try:
                tavily_results = self.tavily_search.invoke(user_query)
                state.tavily_results = tavily_results

                print(f"[TAVILY] Retrieved {len(tavily_results)} external results")

                state.tool_calls.append(ToolCallResult(
                    tool_name="Tavily Search",
                    success=True,
                    result={"num_results": len(tavily_results)},
                    error=None
                ))

            except Exception as e:
                print(f"[ERROR] Tavily search failed: {e}")
                state.tool_calls.append(ToolCallResult(
                    tool_name="Tavily Search",
                    success=False,
                    result=None,
                    error=str(e)
                ))

        # Step 4: Compile context for generation
        context_parts = []

        # Add RAG context
        if state.rag_results:
            context_parts.append("=== Product Information from Database ===")
            for i, result in enumerate(state.rag_results, 1):
                context_parts.append(f"\n[Source {i}] (Relevance: {result.similarity_score:.2f})")
                context_parts.append(result.document_text)

        # Add Tavily context
        if state.tavily_results:
            context_parts.append("\n\n=== External Information ===")
            for i, result in enumerate(state.tavily_results, 1):
                context_parts.append(f"\n[External Source {i}]")
                context_parts.append(result.get('content', ''))

        state.context = "\n".join(context_parts)

        return state

    def _generation_node(self, state: AgentState) -> AgentState:
        """
        Node C: Response Generation

        This node synthesizes all available information (RAG + Tavily)
        into a coherent, helpful response using OpenAI LLM.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with final response
        """
        print("[NODE] Generation...")

        user_query = state.user_query
        context = state.context

        # Create generation prompt
        generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful product information assistant.

Your role is to answer user questions about products based on the provided context.

IMPORTANT INSTRUCTIONS:
1. Use the context provided to answer the question accurately
2. If external web results are provided, prioritize them for shopping/purchase queries
3. For shopping queries, provide specific links and purchasing information when available
4. Synthesize information from both database and web sources when relevant
5. Be concise but informative and always helpful

Context:
{context}"""),
            ("human", "{query}")
        ])

        try:
            # Call LLM for generation
            messages = generation_prompt.format_messages(
                context=context if context else "No specific product information available.",
                query=user_query
            )

            response = self.llm.invoke(messages)
            final_response = response.content

            state.final_response = final_response
            state.workflow_complete = True

            print("[GENERATION] Response generated successfully")

        except Exception as e:
            print(f"[ERROR] Generation failed: {e}")
            state.final_response = (
                "I apologize, but I'm having trouble generating a response. "
                "Please try again or rephrase your question."
            )
            state.workflow_complete = True

        return state

    def query(self, user_query: str) -> Dict[str, Any]:
        """
        Process a user query through the LangGraph workflow.

        Args:
            user_query: User's question

        Returns:
            Dictionary containing response and metadata
        """
        print(f"\n{'='*60}")
        print(f"[QUERY] {user_query}")
        print(f"{'='*60}\n")

        # Create initial state
        initial_state = AgentState(user_query=user_query)

        # Run workflow
        try:
            final_state = self.workflow.invoke(initial_state)

            # Extract final response
            response = final_state.get("final_response", "No response generated.")

            # Compile metadata
            metadata = {
                "classification": (
                    final_state.get("topic_classification").dict()
                    if final_state.get("topic_classification") else None
                ),
                "rag_results_count": len(final_state.get("rag_results", [])),
                "tavily_used": final_state.get("tavily_results") is not None,
                "tool_calls": [tc.dict() for tc in final_state.get("tool_calls", [])],
                "conversation_id": final_state.get("conversation_id")
            }

            return {
                "response": response,
                "metadata": metadata,
                "success": True
            }

        except Exception as e:
            print(f"[ERROR] Workflow execution failed: {e}")
            import traceback
            traceback.print_exc()

            return {
                "response": "I apologize, but an error occurred while processing your query.",
                "metadata": {"error": str(e)},
                "success": False
            }

    def chat(self) -> None:
        """
        Start an interactive chat session in the console.
        """
        print("\n" + "="*60)
        print("PRODUCT RAG CHATBOT - Interactive Session")
        print("="*60)
        print(f"Product Context: {self.product_context}")
        print(f"Model: {self.model_name}")
        print("\nType your questions below. Type 'quit' or 'exit' to end the session.")
        print("="*60 + "\n")

        while True:
            try:
                # Get user input
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                # Check for exit commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n[INFO] Ending chat session. Goodbye!")
                    break

                # Process query
                result = self.query(user_input)

                # Display response
                print(f"\nAssistant: {result['response']}")

                # Optionally display metadata
                if result.get('metadata'):
                    classification = result['metadata'].get('classification')
                    if classification:
                        print(f"\n[Meta] Classification: {classification.get('classification')} "
                              f"(confidence: {classification.get('confidence', 0):.2f})")

                    rag_count = result['metadata'].get('rag_results_count', 0)
                    tavily_used = result['metadata'].get('tavily_used', False)
                    print(f"[Meta] Sources: {rag_count} RAG results" +
                          (", Tavily search used" if tavily_used else ""))

            except KeyboardInterrupt:
                print("\n\n[INFO] Chat interrupted. Goodbye!")
                break
            
            except EOFError:
                print("\n[INFO] Input ended. Goodbye!")
                break

            except Exception as e:
                print(f"\n[ERROR] An error occurred: {e}")
                import traceback
                traceback.print_exc()


def main():
    """
    Main function for standalone chatbot testing.
    """
    try:
        # Initialize data processor
        print("[INFO] Initializing data processor...")
        data_processor = DataProcessor(
            db_path="data/product_capture.db",
            use_mongodb=False
        )

        # Ensure vector store is initialized
        if not data_processor.get_vector_store():
            print("[INFO] Vector store not found. Initializing...")
            data_processor.initialize_vector_store()

        # Create chatbot
        print("[INFO] Creating RAG chatbot...")
        chatbot = ProductRAGChatbot(
            data_processor=data_processor,
            product_context="Product X - Multi-angle captured products"
        )

        # Start interactive chat
        chatbot.chat()

    except Exception as e:
        print(f"[FATAL ERROR] Failed to initialize chatbot: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
